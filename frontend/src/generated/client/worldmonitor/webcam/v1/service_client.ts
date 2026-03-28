// Stub - variant removed
export class WebcamServiceClient {
  constructor(..._args: any[]) {
    return new Proxy(this, {
      get: (_target, _prop) => (..._a: any[]) => Promise.resolve({})
    });
  }
}
export type GetWebcamImageResponse = any;
export type ListWebcamsResponse = any;
export type WebcamCluster = any;
export type WebcamEntry = any;
