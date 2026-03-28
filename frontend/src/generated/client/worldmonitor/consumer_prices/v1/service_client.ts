// Stub - variant removed
export class ConsumerPricesServiceClient {
  constructor(..._args: any[]) {
    return new Proxy(this, {
      get: (_target, _prop) => (..._a: any[]) => Promise.resolve({})
    });
  }
}
export type BasketPoint = any;
export type CategorySnapshot = any;
export type GetConsumerPriceBasketSeriesResponse = any;
export type GetConsumerPriceFreshnessResponse = any;
export type GetConsumerPriceOverviewResponse = any;
export type ListConsumerPriceCategoriesResponse = any;
export type ListConsumerPriceMoversResponse = any;
export type ListRetailerPriceSpreadsResponse = any;
export type PriceMover = any;
export type RetailerFreshnessInfo = any;
export type RetailerSpread = any;
