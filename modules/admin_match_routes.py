"""Route Admin xử lý tranh chấp, sửa tỷ số/trạng thái và xác nhận trận.

Module đăng ký route theo dependency của app.py để giữ nguyên endpoint và tránh import vòng.
"""

from flask import abort

def register_routes(context):
    """Đăng ký nhóm route vào Flask app hiện tại."""
    globals().update(context)

    @app.route("/admin/dispute/<dispute_id>/accept", methods=["POST"])
    @login_required
    @admin_required
    @admin_permission_required("disputes_manage")
    def admin_dispute_accept(dispute_id):
        abort(404)
        dispute = get_match_dispute(dispute_id)
        if not dispute or dispute.get("status") not in DISPUTE_PENDING_STATUSES:
            flash("Tranh chấp không còn hiệu lực.", "warning")
            return redirect_admin("disputes")
        actor = current_user()
        try:
            delta1, delta2 = resolve_match_dispute_with_result(
                dispute,
                dispute.get("submitted_score1"),
                dispute.get("submitted_score2"),
                actor.get("id"),
                "accepted_original",
                request.form.get("resolution_note", "").strip() or "Admin công nhận kết quả ban đầu.",
            )
        except Exception as exc:
            flash(f"Không thể xử lý tranh chấp: {exc}", "danger")
            return redirect_admin("disputes")
        log_admin_action("Công nhận kết quả tranh chấp", "match", dispute.get("match_id"), details=f"Điểm: {delta1:+d}/{delta2:+d}")
        flash("Đã công nhận kết quả và cập nhật điểm.", "success")
        return redirect_admin("disputes")




    @app.route("/admin/dispute/<dispute_id>/cancel", methods=["POST"])
    @login_required
    @admin_required
    @admin_permission_required("disputes_manage")
    def admin_dispute_cancel(dispute_id):
        abort(404)
        dispute = get_match_dispute(dispute_id)
        if not dispute or dispute.get("status") not in DISPUTE_PENDING_STATUSES:
            flash("Tranh chấp không còn hiệu lực.", "warning")
            return redirect_admin("disputes")
        actor = current_user()
        note = request.form.get("resolution_note", "").strip() or "Admin hủy trận tranh chấp; không tính điểm."
        try:
            cancel_match_dispute(dispute, actor.get("id"), note)
        except Exception as exc:
            flash(f"Không thể hủy trận tranh chấp: {exc}", "danger")
            return redirect_admin("disputes")
        log_admin_action("Hủy trận tranh chấp", "match", dispute.get("match_id"), details=note)
        flash("Đã hủy trận tranh chấp. Không ai bị cộng hoặc trừ điểm.", "success")
        return redirect_admin("disputes")



    @app.route("/admin/match/<match_id>/update", methods=["POST"])
    @login_required
    @admin_required
    def admin_update_match(match_id):
        """Admin sửa tỷ số/trạng thái và tính lại BXH theo thời gian trận gốc."""
        actor = current_user()
        match = get_match(match_id)
        if not match:
            flash("Không tìm thấy trận.", "danger")
            return redirect_admin("matches")

        old_signature = _match_state_signature(match)
        old_status = str(match.get("status") or "waiting_confirm")
        new_status = str(request.form.get("status") or old_status).strip()
        note = str(request.form.get("note") or "").strip()[:500]
        allowed_statuses = {"playing", "waiting_confirm", "disputed", "confirmed", "cancelled"}
        if new_status not in allowed_statuses:
            flash("Trạng thái không hợp lệ.", "danger")
            return redirect_admin("matches")

        try:
            new_score1 = parse_score(request.form.get("score1"))
            new_score2 = parse_score(request.form.get("score2"))
        except ValueError as exc:
            flash(str(exc), "danger")
            return redirect_admin("matches")

        if new_status == "confirmed" and not has_admin_permission(actor, "matches_confirm"):
            abort(403)
        if new_status == "cancelled" and not has_admin_permission(actor, "matches_cancel"):
            abort(403)
        if new_status not in {"confirmed", "cancelled"} and not (
            has_admin_permission(actor, "matches_confirm")
            or has_admin_permission(actor, "matches_cancel")
        ):
            abort(403)
        if new_status == "confirmed" and (new_score1 is None or new_score2 is None):
            flash("Trận xác nhận phải có đủ hai tỷ số.", "danger")
            return redirect_admin("matches")

        changed_score = score_changed(match, new_score1, new_score2)
        changed_status = new_status != old_status
        changed_note = note != str(match.get("note") or "")
        if not (changed_score or changed_status or changed_note):
            flash("Không có thay đổi cần lưu.", "warning")
            return redirect_admin("matches")

        override = {
            "score1": new_score1,
            "score2": new_score2,
            "status": new_status,
            "note": note or match.get("note") or (
                "Đã xác nhận." if new_status == "confirmed" else "Admin đã cập nhật trận."
            ),
        }
        if changed_score or changed_status:
            override["confirmed_by_id"] = actor.get("id") if new_status == "confirmed" else None

        lock_token = None
        try:
            if changed_score or changed_status:
                lock_token = acquire_ranking_rebuild_lock(actor.get("id"), match_id)
                fresh = get_match(match_id)
                if not fresh or _match_state_signature(fresh) != old_signature:
                    raise ValueError(
                        "Trận vừa được một luồng khác cập nhật. Hãy tải lại trang trước khi lưu."
                    )
                match = fresh
                old_status = str(match.get("status") or old_status)

            affects_ranking = old_status == "confirmed" or new_status == "confirmed"
            if affects_ranking and (changed_score or changed_status):
                match_count, user_count = rebuild_rankings_after_admin_change(
                    match_id, override, lock_token=lock_token, actor_id=actor.get("id")
                )
                log_admin_action(
                    "Sửa kết quả/trạng thái trận",
                    "match",
                    match_id,
                    details=(
                        f"{match.get('score1')}-{match.get('score2')} / {old_status} → "
                        f"{new_score1}-{new_score2} / {new_status}; phát lại {match_count} trận, "
                        f"tính lại {user_count} tài khoản; giữ nguyên created_at"
                    ),
                )
                flash(
                    "Đã lưu và tính lại RP, thắng/thua, streak, loss_streak theo đúng mốc thời gian cũ.",
                    "success",
                )
                return redirect_admin("matches")

            payload = {key: value for key, value in override.items() if key != "created_at"}
            payload["updated_at"] = now_iso()
            result = execute_query(
                db.table("matches").update(payload).eq("id", match_id).eq("status", old_status),
                "admin_update_match_without_rebuild",
            )
            if not (result.data or []):
                raise ValueError("Trạng thái trận đã thay đổi; chưa ghi đè dữ liệu mới.")
            sync_room_after_admin_match_change(match, override, actor_id=actor.get("id"))
            cache_delete("_rz_matches_all", "_rz_rooms_all")
            ttl_cache_delete("rooms_raw")
            log_admin_action(
                "Cập nhật trận", "match", match_id,
                details=f"{old_status} → {new_status}; giữ nguyên created_at",
            )
            flash("Đã lưu tỷ số, trạng thái và ghi chú. Thời gian trận được giữ nguyên.", "success")
        except ValueError as exc:
            flash(str(exc), "warning")
        except Exception as exc:
            app.logger.exception("admin_update_match failed: %s", exc)
            flash(
                "Không thể cập nhật hoàn chỉnh. Hệ thống đã dừng để tránh cộng/trừ RP sai.",
                "danger",
            )
        finally:
            release_ranking_rebuild_lock(lock_token)
        return redirect_admin("matches")


    @app.route("/admin/cancel/<match_id>", methods=["POST"])
    @login_required
    @admin_required
    @admin_permission_required("matches_cancel")
    def admin_cancel(match_id):
        actor = current_user()
        lock_token = None
        try:
            lock_token = acquire_ranking_rebuild_lock(actor.get("id"), match_id)
            match = get_match(match_id)
            if not match:
                raise ValueError("Không tìm thấy trận.")

            if match.get("status") == "disputed":
                dispute = get_match_dispute_by_match(match_id, DISPUTE_PENDING_STATUSES)
                if dispute:
                    cancel_match_dispute(
                        dispute, actor.get("id"), "Admin hủy trận tranh chấp; không tính điểm."
                    )
                    log_admin_action("Hủy trận tranh chấp", "match", match_id, details="Không tính điểm.")
                    flash("Đã hủy trận tranh chấp. Không ai bị cộng hoặc trừ điểm.", "success")
                    return redirect_admin("disputes")

            override = {
                "status": "cancelled",
                "confirmed_by_id": None,
                "note": "Admin đã hủy trận.",
            }
            if match.get("status") == "confirmed":
                rebuild_rankings_after_admin_change(
                    match_id, override, lock_token=lock_token, actor_id=actor.get("id")
                )
            else:
                payload = {**override, "delta1": 0, "delta2": 0,
                           "winner_id": None, "loser_id": None,
                           "rp_formula_version": None, "rp_details": None,
                           "updated_at": now_iso()}
                result = execute_query(
                    db.table("matches").update(payload).eq("id", match_id).eq("status", match.get("status")),
                    "admin_cancel_match",
                )
                if not (result.data or []):
                    raise ValueError("Trạng thái trận đã thay đổi; chưa hủy trận.")
                sync_room_after_admin_match_change(match, override, actor_id=actor.get("id"))

            log_admin_action("Hủy trận", "match", match_id, details=f"Trạng thái cũ: {match.get('status')}")
            flash("Đã hủy trận và tính lại lịch sử liên quan.", "success")
        except ValueError as exc:
            flash(str(exc), "warning")
        except Exception as exc:
            app.logger.exception("admin_cancel failed: %s", exc)
            flash("Không thể hủy trận an toàn; chưa tiếp tục để tránh sai RP.", "danger")
        finally:
            release_ranking_rebuild_lock(lock_token)
        return redirect_admin("matches")


    @app.route("/admin/confirm-disputed/<match_id>", methods=["POST"])
    @login_required
    @admin_required
    @admin_permission_required("matches_confirm")
    def admin_confirm_disputed(match_id):
        match = get_match(match_id)
        if not match:
            flash("Không tìm thấy trận.", "danger")
            return redirect_admin("matches")

        if match["status"] != "disputed":
            flash("Trận này không phải tranh chấp.", "danger")
            return redirect_admin("matches")

        dispute = get_match_dispute_by_match(match_id, DISPUTE_PENDING_STATUSES)
        if dispute:
            try:
                resolve_match_dispute_with_result(
                    dispute,
                    match.get("score1"),
                    match.get("score2"),
                    current_user().get("id"),
                    "accepted_original",
                    "Admin công nhận kết quả ban đầu.",
                )
            except Exception as exc:
                flash(f"Không thể xử lý tranh chấp: {exc}", "danger")
                return redirect_admin("disputes")
        else:
            lock_token = None
            try:
                lock_token = acquire_ranking_rebuild_lock(current_user().get("id"), match_id)
                rebuild_rankings_after_admin_change(
                    match_id,
                    {
                        "score1": match.get("score1"),
                        "score2": match.get("score2"),
                        "status": "confirmed",
                        "confirmed_by_id": current_user().get("id"),
                        "note": "Admin công nhận kết quả tranh chấp.",
                    },
                    lock_token=lock_token,
                    actor_id=current_user().get("id"),
                )
            except Exception as exc:
                flash(f"Không thể xử lý tranh chấp: {exc}", "danger")
                return redirect_admin("disputes")
            finally:
                release_ranking_rebuild_lock(lock_token)
        log_admin_action("Xác nhận tranh chấp", "match", match_id, details="Đã phát lại lịch sử và cập nhật điểm.")
        flash("Admin đã xác nhận trận tranh chấp.", "success")
        return redirect_admin("disputes")

