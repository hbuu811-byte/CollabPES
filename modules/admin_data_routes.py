"""Route Admin xóa trận, hủy/xóa phòng và xóa lời mời.

Module đăng ký route theo dependency của app.py để giữ nguyên endpoint và tránh import vòng.
"""

def register_routes(context):
    """Đăng ký nhóm route vào Flask app hiện tại."""
    globals().update(context)

    @app.route("/admin/match/<match_id>/delete", methods=["POST"])
    @login_required
    @admin_required
    @admin_permission_required("matches_delete")
    def admin_delete_match(match_id):
        actor = current_user()
        lock_token = None
        try:
            lock_token = acquire_ranking_rebuild_lock(actor.get("id"), match_id)
            match = get_match(match_id)
            if not match:
                raise ValueError("Không tìm thấy trận.")

            if match.get("status") == "confirmed":
                rebuild_rankings_after_admin_change(
                    match_id,
                    {
                        "status": "cancelled",
                        "confirmed_by_id": None,
                        "note": "Admin chuẩn bị xóa trận; đã hoàn tác trong lịch sử.",
                    },
                    lock_token=lock_token,
                    actor_id=actor.get("id"),
                )

            remove_match_dispute_evidence(match_id)
            execute_query(
                db.table("match_rooms").update({
                    "status": "cancelled",
                    "match_id": None,
                    "confirmed_by_id": None,
                    "state_expires_at": None,
                    "note": "Admin đã xóa trận liên kết.",
                    "updated_at": now_iso(),
                }).eq("match_id", match_id),
                "admin_unlink_room_before_delete_match",
                attempts=2,
            )
            execute_query(
                db.table("matches").delete().eq("id", match_id),
                "admin_delete_match_after_rebuild",
            )
            cache_delete("_rz_matches_all", "_rz_rooms_all")
            ttl_cache_delete("rooms_raw")
            log_admin_action(
                "Xóa trận", "match", match_id,
                details=f"Trạng thái cũ: {match.get('status')}; đã phát lại lịch sử trước khi xóa",
            )
            flash("Đã xóa trận và tính lại RP, streak, loss_streak theo lịch sử còn lại.", "success")
        except ValueError as exc:
            flash(str(exc), "warning")
        except Exception as exc:
            app.logger.exception("admin_delete_match failed: %s", exc)
            flash("Không thể xóa trận an toàn; thao tác đã dừng để tránh sai lịch sử.", "danger")
        finally:
            release_ranking_rebuild_lock(lock_token)
        return redirect_admin("matches")


    @app.route("/admin/room/<room_id>/cancel", methods=["POST"])
    @login_required
    @admin_required
    @admin_permission_required("rooms_manage")
    def admin_cancel_room(room_id):
        room = get_room(room_id)
        if not room:
            flash("Không tìm thấy phòng.", "danger")
            return redirect_admin("rooms")

        db.table("match_rooms").update({
            "status": "cancelled",
            "note": "Admin đã hủy phòng.",
            "state_expires_at": None,
            "updated_at": now_iso(),
        }).eq("id", room_id).execute()

        if room.get("match_id"):
            linked_match = get_match(room.get("match_id"))
            if linked_match and linked_match.get("status") == "confirmed":
                if not reverse_confirmed_match_result(linked_match):
                    flash("Không thể hoàn tác RP của trận đã xác nhận; phòng chưa bị hủy.", "danger")
                    return redirect_admin("rooms")
            db.table("matches").update({
                "status": "cancelled",
                "delta1": 0,
                "delta2": 0,
                "note": "Admin đã hủy phòng/trận và hoàn tác RP.",
                "updated_at": now_iso(),
            }).eq("id", room["match_id"]).execute()

        log_admin_action("Hủy phòng", "room", room_id, details=f"Trạng thái cũ: {room.get('status')}")
        flash("Đã hủy phòng.", "success")
        return redirect_admin("rooms")


    @app.route("/admin/room/<room_id>/delete", methods=["POST"])
    @login_required
    @admin_required
    @admin_permission_required("rooms_manage")
    def admin_delete_room(room_id):
        room = get_room(room_id)
        if not room:
            flash("Không tìm thấy phòng.", "danger")
            return redirect_admin("rooms")

        delete_room_safe(room_id)
        log_admin_action("Xóa phòng", "room", room_id, details=f"{room.get('host_name')} vs {room.get('guest_name')}")
        flash("Đã xóa phòng và dữ liệu trận liên quan.", "success")
        return redirect_admin("rooms")


    @app.route("/admin/invite/<invite_id>/delete", methods=["POST"])
    @login_required
    @admin_required
    @admin_permission_required("invites_manage")
    def admin_delete_invite(invite_id):
        invite = get_invite(invite_id)
        if not invite:
            flash("Không tìm thấy lời mời.", "danger")
            return redirect_admin("rooms")

        db.table("match_invites").delete().eq("id", invite_id).execute()
        log_admin_action("Xóa lời mời", "invite", invite_id, details=f"{invite.get('from_name', '-')} → {invite.get('to_name', '-')}")
        flash("Đã xóa lời mời.", "success")
        return redirect_admin("rooms")

