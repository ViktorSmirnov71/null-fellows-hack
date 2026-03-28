// Stub - variant removed
export class HealthServiceClient {
  constructor(..._args: any[]) {
    return new Proxy(this, {
      get: (_target, _prop) => (..._a: any[]) => Promise.resolve({})
    });
  }
}
export type DiseaseOutbreakItem = any;
export type ListDiseaseOutbreaksResponse = any;
