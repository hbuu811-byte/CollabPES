-- RankZone FC V1.10.39
-- Sửa toàn bộ trận confirmed có delta sai dấu hoặc bằng 0.
-- Đồng thời hiệu chỉnh rank_points hiện tại đúng bằng phần chênh lệch delta.
-- Script an toàn khi chạy lại: lần chạy sau sẽ không trừ/cộng lặp.

begin;

create temporary table rz_rp_repair on commit drop as
select
    m.id as match_id,
    m.player1_id,
    m.player2_id,
    coalesce(m.delta1, 0)::integer as old_delta1,
    coalesce(m.delta2, 0)::integer as old_delta2,
    case
        when m.score1 > m.score2 then
            case when coalesce(m.delta1, 0) > 0 then m.delta1::integer else 21 end
        when m.score1 < m.score2 then -20
        else 0
    end as new_delta1,
    case
        when m.score2 > m.score1 then
            case when coalesce(m.delta2, 0) > 0 then m.delta2::integer else 21 end
        when m.score2 < m.score1 then -20
        else 0
    end as new_delta2
from public.matches m
where m.status = 'confirmed'
  and m.score1 is not null
  and m.score2 is not null
  and (
      coalesce(m.delta1, 0) <> case
          when m.score1 > m.score2 then case when coalesce(m.delta1, 0) > 0 then m.delta1::integer else 21 end
          when m.score1 < m.score2 then -20
          else 0
      end
      or
      coalesce(m.delta2, 0) <> case
          when m.score2 > m.score1 then case when coalesce(m.delta2, 0) > 0 then m.delta2::integer else 21 end
          when m.score2 < m.score1 then -20
          else 0
      end
  );

-- Hiệu chỉnh điểm hiện tại đúng bằng phần delta còn thiếu/sai.
with point_changes as (
    select player1_id as user_id, (new_delta1 - old_delta1) as change from rz_rp_repair
    union all
    select player2_id as user_id, (new_delta2 - old_delta2) as change from rz_rp_repair
), totals as (
    select user_id, sum(change)::integer as total_change
    from point_changes
    group by user_id
)
update public.users u
set rank_points = greatest(0, coalesce(u.rank_points, 0) + totals.total_change)
from totals
where u.id = totals.user_id
  and totals.total_change <> 0;

update public.matches m
set delta1 = r.new_delta1,
    delta2 = r.new_delta2,
    updated_at = now()
from rz_rp_repair r
where m.id = r.match_id;

commit;

-- Kết quả mong đợi sau khi chạy: không còn dòng nào.
select id, score1, score2, delta1, delta2
from public.matches
where status = 'confirmed'
  and score1 is not null
  and score2 is not null
  and (
      (score1 > score2 and not (delta1 > 0 and delta2 < 0))
      or (score2 > score1 and not (delta2 > 0 and delta1 < 0))
      or (score1 = score2 and not (delta1 = 0 and delta2 = 0))
  );
