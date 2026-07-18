"""Route bỏ cuộc và đá lại trong phòng đấu.

Module đăng ký route theo dependency của app.py để giữ nguyên endpoint và tránh import vòng.
"""

def register_routes(context):
    """Đăng ký nhóm route vào Flask app hiện tại."""
    globals().update(context)

    @app.route("/room/<room_id>/guest-forfeit", methods=["POST"])
    @login_required
    def room_guest_forfeit(room_id):
        """Khách chủ động bỏ cuộc sau khi đã chấp nhận vào phòng hoặc sau khi quay đội."""
        user = current_user()
        room = get_room(room_id)

        if not room:
            flash("Không tìm thấy phòng.", "danger")
            return redirect(url_for("dashboard"))

        if user["id"] != room.get("guest_user_id"):
            flash("Chỉ người chơi Sân Khách mới có thể dùng chức năng này.", "danger")
            return redirect(url_for("room_detail", room_id=room_id))

        allowed_statuses = {"waiting_ready", "playing", "friendly_playing", "waiting_result_confirm"}
        if room.get("status") not in allowed_statuses:
            flash("Phòng hiện không ở trạng thái có thể bỏ cuộc.", "warning")
            return redirect(url_for("room_detail", room_id=room_id))

        # Ở trạng thái chờ, chỉ bắt đầu áp dụng phạt sau khi khách đã bấm Sẵn Sàng.
        # Giao diện sẽ đưa khách chưa sẵn sàng qua route room_leave để rời phòng không mất RP.
        # Kiểm tra này bảo vệ cả trường hợp người dùng tự gửi POST trực tiếp vào route bỏ cuộc.
        if room.get("status") == "waiting_ready" and not bool(room.get("guest_ready")):
            flash("Bạn chưa Sẵn Sàng nên có thể rời phòng mà không bị trừ RP.", "warning")
            return redirect(url_for("room_detail", room_id=room_id))

        original_status = room.get("status")
        reason = f'{user["display_name"]} đã chủ động bỏ cuộc và bị trừ {ROOM_ABANDON_PENALTY} RP.'
        result = execute_query(
            db.table("match_rooms").update({
                "status": "cancelled",
                "guest_ready": False,
                "note": reason,
                "state_expires_at": None,
                "updated_at": now_iso(),
            }).eq("id", room_id).eq("status", original_status),
            "guest_forfeit_room",
        )

        # Điều kiện status giúp tránh bấm hai lần và bị trừ RP nhiều lần.
        if not (result.data or []):
            flash("Phòng đã được xử lý trước đó. Bạn không bị trừ điểm thêm.", "warning")
            return redirect(url_for("dashboard"))

        penalty_delta = apply_room_abandon_penalty(user["id"])
        if room.get("match_id"):
            execute_query(
                db.table("matches").update({
                    "status": "cancelled",
                    "delta1": 0,
                    "delta2": penalty_delta if penalty_delta is not None else -ROOM_ABANDON_PENALTY,
                    "note": reason,
                    "updated_at": now_iso(),
                }).eq("id", room.get("match_id")),
                "guest_forfeit_match",
            )

        create_user_notification(
            room.get("host_user_id"),
            "🚪 Đối thủ đã bỏ cuộc",
            f'{user["display_name"]} đã thoát phòng và bị trừ {ROOM_ABANDON_PENALTY} RP. Bạn không bị cộng hoặc trừ RP.',
            "/matches",
            "guest_forfeit",
        )
        create_user_notification(
            user["id"],
            "⚠️ Bạn đã bỏ cuộc",
            f"Bạn bị trừ {ROOM_ABANDON_PENALTY} RP và được tính một trận thua.",
            "/matches",
            "room_forfeit_penalty",
        )
        flash(f"Bạn đã bỏ cuộc và bị trừ {ROOM_ABANDON_PENALTY} RP.", "danger")
        return redirect(url_for("dashboard"))


    @app.route("/room/<room_id>/rematch", methods=["POST"])
    @login_required
    def room_rematch(room_id):
        user = current_user()
        room = get_room(room_id)

        if not room:
            flash("Không tìm thấy phòng.", "danger")
            return redirect(url_for("dashboard"))

        if user["id"] not in [room["host_user_id"], room["guest_user_id"]]:
            flash("Bạn không thuộc phòng này.", "danger")
            return redirect(url_for("dashboard"))

        if room["status"] != "confirmed":
            flash("Chỉ có thể đá tiếp sau khi kết quả trận trước đã được xác nhận.", "warning")
            return redirect(url_for("room_detail", room_id=room_id))

        host_active_room = active_room_for_user(room["host_user_id"], exclude_room_id=room_id)
        guest_active_room = active_room_for_user(room["guest_user_id"], exclude_room_id=room_id)
        host_active_match = active_match_for_user(room["host_user_id"])
        guest_active_match = active_match_for_user(room["guest_user_id"])
        if host_active_room or guest_active_room or host_active_match or guest_active_match:
            flash("Một trong hai người đang có phòng hoặc trận khác nên chưa thể đá tiếp từ phòng này.", "warning")
            return redirect(url_for("room_detail", room_id=room_id))

        is_host = user["id"] == room["host_user_id"]
        my_ready_note = REMATCH_HOST_READY_NOTE if is_host else REMATCH_GUEST_READY_NOTE
        opponent_ready_note = REMATCH_GUEST_READY_NOTE if is_host else REMATCH_HOST_READY_NOTE
        current_note = room.get("note") or ""

        if current_note in {REMATCH_HOST_DECLINED_NOTE, REMATCH_GUEST_DECLINED_NOTE}:
            flash("Đối thủ đã chọn không đá tiếp. Phiên đá tiếp đã kết thúc.", "warning")
            return redirect(url_for("dashboard"))

        if current_note == REMATCH_EXPIRED_NOTE:
            flash("Yêu cầu đá tiếp đã hết hạn sau 60 giây.", "warning")
            return redirect(url_for("dashboard"))

        if current_note == my_ready_note:
            flash("Bạn đã chọn Đá tiếp. Đang chờ đối thủ xác nhận.", "warning")
            return redirect(url_for("room_detail", room_id=room_id))

        # Khách bấm Đá tiếp: khách được tính là sẵn sàng ngay và chủ phòng thấy nút quay đội Xếp hạng.
        if not is_host:
            execute_query(
                db.table("match_rooms").update({
                    "host_team": None,
                    "guest_team": None,
                    "host_team_overall": None,
                    "guest_team_overall": None,
                    "host_team_logo_url": None,
                    "guest_team_logo_url": None,
                    "host_team_league": None,
                    "guest_team_league": None,
                    "guest_ready": True,
                    "status": "waiting_ready",
                    "match_id": None,
                    "host_score": None,
                    "guest_score": None,
                    "submitted_by_id": None,
                    "confirmed_by_id": None,
                    "match_mode": MATCH_MODE_RANKED,
                    "team_tier": SMART_RANDOM_MODE,
                    "note": "Khách đã chọn đá tiếp và sẵn sàng. Chủ phòng có thể quay đội Xếp hạng.",
                    "state_expires_at": None,
                    "updated_at": now_iso(),
                }).eq("id", room_id).eq("status", "confirmed"),
                "room_guest_rematch_ready_for_ranked_random",
            )
            flash("Bạn đã chọn Đá tiếp. Chủ phòng có thể quay đội Xếp hạng ngay.", "success")
            return redirect(url_for("room_detail", room_id=room_id))

        # Người đầu tiên bấm Đá tiếp: ghi nhận ngay trong phòng, không tạo lời mời mới.
        if current_note != opponent_ready_note:
            execute_query(
                db.table("match_rooms").update({
                    "note": my_ready_note,
                    "state_expires_at": future_iso(REMATCH_TIMEOUT_SECONDS),
                    "updated_at": now_iso(),
                }).eq("id", room_id).eq("status", "confirmed"),
                "room_rematch_first_ready",
            )
            flash("Bạn đã chọn Đá tiếp. Đang chờ đối thủ bấm Đá tiếp.", "success")
            return redirect(url_for("room_detail", room_id=room_id))

        # Người thứ hai đồng ý: dùng lại chính phòng hiện tại và đưa cả hai về bước random đội.
        host_active_room = active_room_for_user(room["host_user_id"], exclude_room_id=room_id)
        guest_active_room = active_room_for_user(room["guest_user_id"], exclude_room_id=room_id)
        if host_active_room or guest_active_room:
            flash("Một trong hai người đang có phòng khác chưa hoàn tất nên chưa thể đá tiếp.", "warning")
            return redirect(url_for("room_detail", room_id=room_id))

        # Hủy lời mời chờ cũ giữa hai người (nếu còn từ phiên bản trước), tránh hiện thông báo thừa.
        for from_user_id, to_user_id in [
            (room["host_user_id"], room["guest_user_id"]),
            (room["guest_user_id"], room["host_user_id"]),
        ]:
            try:
                db.table("match_invites").update({
                    "status": "cancelled",
                    "updated_at": now_iso(),
                }).eq("from_user_id", from_user_id).eq("to_user_id", to_user_id).eq("status", "pending").execute()
            except Exception as exc:
                print(f"Rematch pending invite cleanup warning: {exc}")

        execute_query(
            db.table("match_rooms").update({
                "host_team": None,
                "guest_team": None,
                "guest_ready": True,
                "status": "waiting_ready",
                "match_id": None,
                "host_score": None,
                "guest_score": None,
                "submitted_by_id": None,
                "confirmed_by_id": None,
                "team_tier": SMART_RANDOM_MODE,
                "note": "Hai người đã đồng ý đá tiếp. Đang chờ Chủ Phòng quay đội.",
                "state_expires_at": None,
                "updated_at": now_iso(),
            }).eq("id", room_id).eq("status", "confirmed"),
            "room_rematch_reset_same_room",
        )

        flash("Cả hai đã đồng ý đá tiếp. Đang chờ Chủ Phòng quay đội.", "success")
        return redirect(url_for("room_detail", room_id=room_id))


    @app.route("/room/<room_id>/rematch-decline", methods=["POST"])
    @login_required
    def room_rematch_decline(room_id):
        user = current_user()
        room = get_room(room_id)

        if not room:
            flash("Không tìm thấy phòng.", "danger")
            return redirect(url_for("dashboard"))

        if user["id"] not in [room["host_user_id"], room["guest_user_id"]]:
            flash("Bạn không thuộc phòng này.", "danger")
            return redirect(url_for("dashboard"))

        if room["status"] != "confirmed":
            flash("Chỉ có thể từ chối đá tiếp sau khi trận trước đã hoàn tất.", "warning")
            return redirect(url_for("room_detail", room_id=room_id))

        is_host = user["id"] == room["host_user_id"]
        my_ready_note = REMATCH_HOST_READY_NOTE if is_host else REMATCH_GUEST_READY_NOTE
        opponent_ready_note = REMATCH_GUEST_READY_NOTE if is_host else REMATCH_HOST_READY_NOTE
        decline_note = REMATCH_HOST_DECLINED_NOTE if is_host else REMATCH_GUEST_DECLINED_NOTE
        current_note = room.get("note") or ""

        if current_note in {REMATCH_HOST_DECLINED_NOTE, REMATCH_GUEST_DECLINED_NOTE}:
            flash("Phiên đá tiếp đã được từ chối trước đó.", "warning")
            return redirect(url_for("dashboard"))

        # Cho phép rời phòng ngay sau khi kết quả đã xác nhận, kể cả chưa có ai bấm Đá tiếp.

        execute_query(
            db.table("match_rooms").update({
                "note": decline_note,
                "state_expires_at": None,
                "updated_at": now_iso(),
            }).eq("id", room_id).eq("status", "confirmed"),
            "room_rematch_declined",
        )

        flash("Bạn đã rời phòng và trở về sảnh chính.", "success")
        return redirect(url_for("dashboard"))

