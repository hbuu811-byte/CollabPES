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
        """Giữ endpoint cũ nhưng khóa xóa trực tiếp để tránh làm lệch lịch sử."""
        flash(
            "Collap_V1.13.3a đã tắt xóa trực tiếp trận đấu. Admin chỉ được chuyển trạng thái sang Đã hủy.",
            "warning",
        )
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

