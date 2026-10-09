-- Read-only report views for the cloud database (CockroachDB / Postgres), so reports can be queried in the
-- database console with plain SQL — same names and columns as `make export-sqlite`:
--   SELECT * FROM verdict;   SELECT * FROM improvement_plan;   SELECT * FROM call_scores WHERE call_id = 31;
-- They always show the latest data. Installed by an Alembic migration; statements are separated by ";".

CREATE OR REPLACE VIEW calls_report AS
SELECT c.id AS call_id, c.label AS call, c.agent_type::STRING AS agent_type, c.lead_id, l.name AS lead_name,
       c.agent_name, c.campaign, coalesce(c.call_datetime, c.created_at) AS call_datetime, c.duration_s,
       c.status::STRING AS status, c.error_detail AS error,
       (a.result->>'review_score')::FLOAT AS review_score, a.quality_pct, a.intent_score, a.intent_bucket,
       a.result->'outcome'->>'disposition' AS outcome, a.result->'outcome'->>'next_step' AS next_step,
       a.result->'outcome'->>'next_step_when' AS next_step_when, a.result->'mood'->>'start' AS mood_start,
       a.result->'mood'->>'end' AS mood_end, a.result->>'language' AS language,
       a.result->'summary'->>'one_liner' AS summary, a.result->'customer'->>'name' AS customer_name,
       a.result->'customer'->>'city' AS city, a.result->'customer'->>'budget' AS budget,
       a.prompt_version AS reviewed_with
FROM calls c LEFT JOIN analyses a ON a.call_id = c.id LEFT JOIN leads l ON l.id = c.lead_id;

CREATE OR REPLACE VIEW call_scores AS
SELECT c.id AS call_id, c.label AS call, c.agent_type::STRING AS agent_type, sc->>'key' AS dimension,
       (sc->>'score')::INT AS score, sc->>'reason' AS reason, sc->>'evidence' AS quote,
       (sc->>'t')::FLOAT AS at_second, coalesce(sc->>'better', '') AS better
FROM calls c JOIN analyses a ON a.call_id = c.id, jsonb_array_elements(a.result->'scorecard') AS sc;

CREATE OR REPLACE VIEW call_objections AS
SELECT c.id AS call_id, c.label AS call, c.agent_type::STRING AS agent_type, o->>'type' AS type,
       o->>'title' AS title, o->>'customer_quote' AS customer_quote, (o->>'t')::FLOAT AS at_second,
       (o->>'handled_well')::BOOL AS handled_well, o->>'handling' AS handling, o->>'better_response' AS better_response
FROM calls c JOIN analyses a ON a.call_id = c.id, jsonb_array_elements(a.result->'objections') AS o;

CREATE OR REPLACE VIEW call_next_actions AS
SELECT c.id AS call_id, c.label AS call, c.agent_type::STRING AS agent_type, c.lead_id, n->>'title' AS title,
       n->>'say' AS say, n->>'why' AS why, n->>'when' AS due_when, n->>'due' AS due
FROM calls c JOIN analyses a ON a.call_id = c.id, jsonb_array_elements(a.result->'next_actions') AS n;

CREATE OR REPLACE VIEW transcript_lines AS
SELECT t.call_id, (seg->>'i')::INT AS line, (seg->>'start')::FLOAT AS start_s, seg->>'role' AS role,
       seg->>'text' AS text
FROM transcripts t, jsonb_array_elements(t.segments::JSONB) AS seg;

-- The latest AI vs Human report over all calls (as saved by the AI vs Human page).
CREATE OR REPLACE VIEW report_latest AS
SELECT id, created_at, result FROM comparisons
WHERE result ? 'improvement'
  AND result->'scope'->'batch_ids' = '[]'::JSONB
  AND coalesce(result->'scope'->>'campaign', '') = ''
  AND result->'scope'->>'date_from' IS NULL AND result->'scope'->>'date_to' IS NULL
  AND coalesce((result->'scope'->>'comparable_only')::BOOL, false) = false
ORDER BY id DESC LIMIT 1;

CREATE OR REPLACE VIEW verdict AS
SELECT result->>'generated_at' AS generated_at,
       result->'improvement'->'verdict'->>'label' AS verdict,
       (result->'improvement'->'verdict'->>'readiness_pct')::INT AS readiness_pct,
       (result->'improvement'->'verdict'->>'gap')::FLOAT AS gap,
       (result->'scores'->'ai'->>'avg_review')::FLOAT AS bot_avg_score,
       (result->'scores'->'human'->>'avg_review')::FLOAT AS human_avg_score,
       (result->'improvement'->'verdict'->'positive_outcome_pct'->>'ai')::INT AS bot_next_step_pct,
       (result->'improvement'->'verdict'->'positive_outcome_pct'->>'human')::INT AS human_next_step_pct,
       result->'synthesis'->>'verdict_headline' AS headline,
       result->'synthesis'->>'verdict_detail' AS assessment,
       result->>'synthesis_error' AS ai_summary_error
FROM report_latest;

CREATE OR REPLACE VIEW verdict_points AS
SELECT p.n AS n, p.point #>> '{}' AS point
FROM report_latest, jsonb_array_elements(result->'improvement'->'verdict'->'points') WITH ORDINALITY AS p(point, n);

CREATE OR REPLACE VIEW improvement_plan AS
SELECT p.rank AS rank, p.v->>'priority' AS priority, p.v->>'label' AS parameter, (p.v->>'ai')::FLOAT AS bot,
       (p.v->>'human')::FLOAT AS humans, (p.v->>'gap')::FLOAT AS gap, (p.v->>'weak_calls')::INT AS weak_bot_calls,
       (p.v->>'of')::INT AS of_bot_calls, p.v->>'area' AS owner, p.v->>'fix' AS how_to_fix
FROM report_latest, jsonb_array_elements(result->'improvement'->'parameters') WITH ORDINALITY AS p(v, rank);

CREATE OR REPLACE VIEW root_causes AS
SELECT c->>'label' AS failure, (c->>'count')::INT AS bot_calls, (c->>'of')::INT AS of_bot_calls,
       (c->>'share')::INT AS share_pct, c->>'priority' AS priority, c->>'area' AS owner, c->>'fix' AS fix
FROM report_latest, jsonb_array_elements(result->'improvement'->'root_causes') AS c;

CREATE OR REPLACE VIEW root_cause_calls AS
SELECT c->>'label' AS failure, (h->>'call_id')::INT AS call_id, h->>'label' AS call, (h->>'lead_id')::INT AS lead_id,
       h->>'description' AS what_happened, h->>'quote' AS quote, (h->>'t')::FLOAT AS at_second, h->>'better' AS better
FROM report_latest, jsonb_array_elements(result->'improvement'->'root_causes') AS c,
     jsonb_array_elements(c->'calls') AS h;

CREATE OR REPLACE VIEW call_rca_issues AS
SELECT (x->>'call_id')::INT AS call_id, x->>'label' AS call, (x->>'lead_id')::INT AS lead_id,
       (x->>'review_score')::FLOAT AS call_score, x->>'outcome' AS outcome, (i->>'t')::FLOAT AS at_second,
       i->>'kind' AS kind, i->>'title' AS issue, i->>'detail' AS what_happened, i->>'quote' AS quote, i->>'better' AS better
FROM report_latest, jsonb_array_elements(result->'improvement'->'call_rca') AS x, jsonb_array_elements(x->'issues') AS i;

CREATE OR REPLACE VIEW recommended_changes AS
SELECT ch->>'priority' AS priority, ch->>'area' AS area, ch->>'change' AS change, ch->>'rationale' AS why,
       ch->>'bot_line' AS new_bot_line
FROM report_latest, jsonb_array_elements(coalesce(result->'synthesis'->'recommended_changes', '[]'::JSONB)) AS ch;
