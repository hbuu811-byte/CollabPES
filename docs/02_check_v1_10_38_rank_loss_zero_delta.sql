-- V1.10.38 check after repair.
-- All counts should be 0.

select
  count(*) filter (
    where status = 'confirmed'
      and score1 is not null and score2 is not null
      and score1 < score2
      and coalesce(delta1, 0) >= 0
  ) as bad_player1_loss_delta,
  count(*) filter (
    where status = 'confirmed'
      and score1 is not null and score2 is not null
      and score2 < score1
      and coalesce(delta2, 0) >= 0
  ) as bad_player2_loss_delta,
  count(*) filter (
    where status = 'confirmed'
      and score1 is not null and score2 is not null
      and score1 > score2
      and coalesce(delta1, 0) <= 0
  ) as bad_player1_win_delta,
  count(*) filter (
    where status = 'confirmed'
      and score1 is not null and score2 is not null
      and score2 > score1
      and coalesce(delta2, 0) <= 0
  ) as bad_player2_win_delta
from public.matches;
