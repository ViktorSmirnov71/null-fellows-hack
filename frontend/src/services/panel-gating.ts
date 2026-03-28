import type { AuthSession } from './auth-state';

export enum PanelGateReason {
  NONE = 'none',
  ANONYMOUS = 'anonymous',
  FREE_TIER = 'free_tier',
}

/** All features unlocked — no premium gating. */
export function hasPremiumAccess(_authState?: AuthSession): boolean {
  return true;
}

/** All panels ungated. */
export function getPanelGateReason(
  _authState: AuthSession,
  _isPremium: boolean,
): PanelGateReason {
  return PanelGateReason.NONE;
}
