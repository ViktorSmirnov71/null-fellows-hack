// Stub - variant removed
export class UnrestServiceClient {
  constructor(..._args: any[]) {
    return new Proxy(this, {
      get: (_target, _prop) => (..._a: any[]) => Promise.resolve({})
    });
  }
}
export type ListUnrestEventsResponse = any;
export type UnrestEvent = any;
