// Stub - variant removed
export class AviationServiceClient {
  constructor(..._args: any[]) {
    return new Proxy(this, {
      get: (_target, _prop) => (..._a: any[]) => Promise.resolve({})
    });
  }
}
export type AirportDelayAlert = any;
export type AirportOpsSummary = any;
export type AviationNewsItem = any;
export type CabinClass = any;
export type CarrierOpsSummary = any;
export type FlightInstance = any;
export type PositionSample = any;
export type PriceQuote = any;
