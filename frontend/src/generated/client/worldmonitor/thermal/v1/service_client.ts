// Stub - variant removed
export class ThermalServiceClient {
  constructor(..._args: any[]) {
    return new Proxy(this, {
      get: (_target, _prop) => (..._a: any[]) => Promise.resolve({})
    });
  }
}
export type ThermalConfidence = any;
export type ThermalContext = any;
export type ThermalEscalationCluster = any;
export type ThermalStatus = any;
export type ThermalStrategicRelevance = any;
