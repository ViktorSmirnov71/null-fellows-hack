// Stub - variant removed
export class ResearchServiceClient {
  constructor(..._args: any[]) {
    return new Proxy(this, {
      get: (_target, _prop) => (..._a: any[]) => Promise.resolve({})
    });
  }
}
export type ArxivPaper = any;
export type GithubRepo = any;
export type HackernewsItem = any;
export type ListTechEventsResponse = any;
export type TechEvent = any;
