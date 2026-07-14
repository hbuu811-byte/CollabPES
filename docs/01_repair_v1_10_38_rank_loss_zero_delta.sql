-- V1.10.38 one-time repair for old confirmed losses saved with +0 / 0 RP.
-- Run once in Supabase SQL Editor AFTER deploying V1.10.38.
-- This only touches confirmed non-draw matches where the losing side has delta >= 0.

begin;

create temp table _v1038_bad_rank_losses as
select id as match_id, player1_id as loser_id, 'delta1'::text as delta_column
from public.matches
where status = 'confirmed'
  and score1 is not null and score2 is not null
  and score1 < score2
  and coalesce(delta1, 0) >= 0
union all
select id as match_id, player2_id as loser_id, 'delta2'::text as delta_column
from public.matches
where status = 'confirmed'
  and score1 is not null and score2 is not null
  and score2 < score1
  and coalesce(delta2, 0) >= 0;

with loss_counts as (
    select loser_id, count(*)::int as bad_loss_count
    from _v1038_bad_rank_losses
    group by loser_id
)
update public.users u
set rank_points = greatest(0, coalesce(u.rank_points, 0) - (loss_counts.bad_loss_count * 20))
from loss_counts
where u.id = loss_counts.loser_id;

update public.matches
set delta1 = -20,
    updated_at = now()
where id in (select match_id from _v1038_bad_rank_losses where delta_column = 'delta1');

update public.matches
set delta2 = -20,
    updated_at = now()
where id in (select match_id from _v1038_bad_rank_losses where delta_column = 'delta2');

commit;
