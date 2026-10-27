import { signedMw, mw, pct, utcLabel } from "./format.js";

test("signed MW keeps the forecast-minus-actual sign", () => {
  expect(signedMw(120)).toBe("+120 MW");
  expect(signedMw(-45)).toBe("−45 MW");
  expect(signedMw(0)).toBe("0 MW");
});
test("missing values show a dash, never zero", () => {
  expect(mw(null)).toBe("–");
  expect(signedMw(undefined)).toBe("–");
  expect(pct(null)).toBe("–");
});
test("UTC label", () => {
  expect(utcLabel("2026-01-05T12:30:00Z")).toBe("2026-01-05 12:30 UTC");
});
