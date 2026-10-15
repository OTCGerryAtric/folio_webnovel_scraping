import { expect, it } from 'vitest'
import { deviceName } from './device'
import { clampSettings, defaults } from './settings'

it('names devices readably', () => {
  expect(deviceName('Mozilla/5.0 (iPhone; CPU iPhone OS 17_0 like Mac OS X) AppleWebKit/605.1.15 Version/17.0 Mobile/15E148 Safari/604.1')).toBe('iPhone · Safari')
  expect(deviceName('Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/141.0 Safari/537.36 Edg/141.0')).toBe('Windows · Edge')
  expect(deviceName('Mozilla/5.0 (Linux; Android 14; Pixel 8) AppleWebKit/537.36 Chrome/141.0 Mobile Safari/537.36')).toBe('Android · Chrome')
  expect(deviceName('Mozilla/5.0 (iPad; CPU OS 17_0 like Mac OS X) AppleWebKit/605.1.15 Version/17.0 Safari/604.1')).toBe('iPad · Safari')
  expect(deviceName('Mozilla/5.0 (Windows NT 10.0; rv:130.0) Gecko/20100101 Firefox/130.0')).toBe('Windows · Firefox')
  expect(deviceName('')).toBe('Browser')
})

it('keeps reader settings in range', () => {
  expect(defaults(true).size).toBe(19)
  expect(defaults(false).size).toBe(20)
  expect(clampSettings({ ...defaults(false), size: 99, leading: 0.5 })).toMatchObject({ size: 26, leading: 1.45 })
  expect(clampSettings({ ...defaults(false), measure: 'huge' as any, theme: 'neon' as any })).toMatchObject({ measure: 'medium', theme: null })
})
