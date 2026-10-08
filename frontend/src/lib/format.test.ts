import { describe, expect, it } from 'vitest'
import { formatClock, formatHoursMins, humanize } from './format'

describe('formatHoursMins', () => {
  it('matches the reference KPI pill', () => {
    expect(formatHoursMins(145 * 3600 + 24 * 60)).toBe('145 hours 24 mins')
  })
  it('drops hours when under one hour', () => {
    expect(formatHoursMins(59)).toBe('0 mins')
    expect(formatHoursMins(61)).toBe('1 min')
  })
  it('uses singular forms', () => {
    expect(formatHoursMins(3600 + 60)).toBe('1 hour 1 min')
  })
})

describe('formatClock', () => {
  it('formats minutes and hours', () => {
    expect(formatClock(93)).toBe('1:33')
    expect(formatClock(3725)).toBe('1:02:05')
    expect(formatClock(-4)).toBe('0:00')
  })
})

describe('humanize', () => {
  it('turns config keys into labels', () => {
    expect(humanize('lack_of_interest')).toBe('Lack of interest')
  })
})
