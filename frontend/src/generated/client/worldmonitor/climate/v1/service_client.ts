// Stub - variant removed
export class ClimateServiceClient {
  constructor(..._args: any[]) {
    return new Proxy(this, {
      get: (_target, _prop) => (..._a: any[]) => Promise.resolve({})
    });
  }
}
export type AnomalySeverity = any;
export type AnomalyType = any;
export type ClimateAnomaly = any;
export type ListClimateAnomaliesResponse = any;
