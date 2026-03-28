// Stub - variant removed
export class RadiationServiceClient {
  constructor(..._args: any[]) {
    return new Proxy(this, {
      get: (_target, _prop) => (..._a: any[]) => Promise.resolve({})
    });
  }
}
export type ListRadiationObservationsResponse = any;
export type RadiationConfidence = any;
export type RadiationFreshness = any;
export type RadiationObservation = any;
export type RadiationSeverity = any;
export type RadiationSource = any;
