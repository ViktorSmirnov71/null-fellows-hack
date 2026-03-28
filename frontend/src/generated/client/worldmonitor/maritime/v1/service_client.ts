// Stub - variant removed
export class MaritimeServiceClient {
  constructor(..._args: any[]) {
    return new Proxy(this, {
      get: (_target, _prop) => (..._a: any[]) => Promise.resolve({})
    });
  }
}
export type AisDensityZone = any;
export type AisDisruption = any;
export type GetVesselSnapshotResponse = any;
export type NavigationalWarning = any;
