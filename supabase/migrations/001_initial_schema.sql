-- User profiles
create table profiles (
  id uuid references auth.users on delete cascade primary key,
  email text not null,
  display_name text,
  annual_income numeric,
  investable_amount numeric,
  risk_tolerance text check (risk_tolerance in ('conservative', 'moderate', 'aggressive')),
  created_at timestamptz default now(),
  updated_at timestamptz default now()
);

-- Portfolio allocations
create table portfolios (
  id uuid default gen_random_uuid() primary key,
  user_id uuid references profiles(id) on delete cascade not null,
  name text not null default 'My Portfolio',
  is_active boolean default true,
  created_at timestamptz default now(),
  updated_at timestamptz default now()
);

-- Individual positions within a portfolio
create table positions (
  id uuid default gen_random_uuid() primary key,
  portfolio_id uuid references portfolios(id) on delete cascade not null,
  ticker text not null,
  weight numeric not null check (weight > 0 and weight <= 1),
  asset_class text not null,
  entry_price numeric,
  current_price numeric,
  updated_at timestamptz default now()
);

-- AutoAllocator experiment log (mirrors experiment_log.tsv)
create table experiments (
  id serial primary key,
  portfolio_id uuid references portfolios(id) on delete cascade,
  experiment_num integer not null,
  status text not null check (status in ('KEPT', 'DISCARDED', 'CRASH')),
  sharpe_ratio numeric,
  sortino_ratio numeric,
  max_drawdown numeric,
  calmar_ratio numeric,
  tail_ratio numeric,
  cagr numeric,
  description text,
  benchmark_sharpe numeric,
  created_at timestamptz default now()
);

-- Risk scores over time
create table risk_scores (
  id serial primary key,
  total numeric not null,
  geopolitical numeric,
  macro numeric,
  volatility numeric,
  components jsonb,
  created_at timestamptz default now()
);

-- Sentiment signals
create table sentiment_signals (
  id serial primary key,
  ticker text,
  sector text,
  direction numeric not null,
  conviction numeric not null,
  source_headline text,
  reasoning text,
  created_at timestamptz default now()
);

-- Row Level Security
alter table profiles enable row level security;
alter table portfolios enable row level security;
alter table positions enable row level security;

create policy "Users can view own profile"
  on profiles for select using (auth.uid() = id);

create policy "Users can update own profile"
  on profiles for update using (auth.uid() = id);

create policy "Users can view own portfolios"
  on portfolios for select using (auth.uid() = user_id);

create policy "Users can view own positions"
  on positions for select using (
    portfolio_id in (select id from portfolios where user_id = auth.uid())
  );
