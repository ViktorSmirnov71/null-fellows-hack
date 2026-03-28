// Stub - variant removed
export class MilitaryServiceClient {
  constructor(..._args: any[]) {
    return new Proxy(this, {
      get: (_target, _prop) => (..._a: any[]) => Promise.resolve({})
    });
  }
}
export type AircraftDetails = any;
export type DefensePatentFiling = any;
export type GetTheaterPostureResponse = any;
export type GetUSNIFleetReportResponse = any;
export type ListMilitaryBasesResponse = any;
export type MilitaryBaseCluster = any;
export type MilitaryBaseEntry = any;
export type TheaterPosture = any;
export type WingbitsLiveFlight = any;
