// Stub - variant removed
export class WildfireServiceClient {
  constructor(..._args: any[]) {
    return new Proxy(this, {
      get: (_target, _prop) => (..._a: any[]) => Promise.resolve({})
    });
  }
}
export type FireConfidence = any;
export type FireDetection = any;
export type ListFireDetectionsResponse = any;
