// Stub - variant removed
export class CyberServiceClient {
  constructor(..._args: any[]) {
    return new Proxy(this, {
      get: (_target, _prop) => (..._a: any[]) => Promise.resolve({})
    });
  }
}
export type CyberThreat = any;
export type ListCyberThreatsResponse = any;
