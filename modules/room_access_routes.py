"""Route truy cập phòng: danh sách phòng, tham gia bằng link, xem phòng và rời phòng.

Module đăng ký route theo dependency của app.py để giữ nguyên endpoint và tránh import vòng.
"""

from flask import get_flashed_messages

def register_routes(context):
    """Đăng ký nhóm route vào Flask app hiện tại."""
    globals().update(context)

    @app.route("/rooms")
    @login_required
    def rooms():
        user = current_user()
        all_rooms = list_rooms()
        my_rooms = [r for r in all_rooms if user["id"] in [r["host_user_id"], r["guest_user_id"]]]
        return render_template("rooms.html", rooms=my_rooms)


    @app.route("/room/join/<room_id>", methods=["GET"])
    def room_join_shared(room_id):
        """Cho phép một tài khoản tham gia phòng trống từ link được chia sẻ.

        Route này tự ghi nhớ phòng nếu người mở link chưa đăng nhập. Việc nhận chỗ
        khách được cập nhật có điều kiện để hai người bấm cùng lúc không thể cùng
        chiếm một phòng.
        """
        if not session.get("user_id"):
            session["pending_room_join_id"] = str(room_id)
            flash("Hãy đăng nhập để tham gia phòng đấu được chia sẻ.", "warning")
            return redirect(url_for("login"))

        user = current_user()
        if not user:
            session.clear()
            session["pending_room_join_id"] = str(room_id)
            flash("Phiên đăng nhập không hợp lệ. Hãy đăng nhập lại để vào phòng.", "warning")
            return redirect(url_for("login"))

        if user.get("account_status", "approved") != "approved":
            session.clear()
            flash("Tài khoản chưa được phép tham gia phòng đấu.", "danger")
            return redirect(url_for("login"))

        try:
            room = get_room(room_id)
        except Exception as exc:
            app.logger.warning("Shared room join load failed room=%s: %s", room_id, exc)
            flash("Phòng đang tải chậm. Vui lòng mở lại link sau vài giây.", "warning")
            return redirect(url_for("dashboard"))

        if not room:
            flash("Link phòng không còn tồn tại hoặc phòng đã bị xóa.", "danger")
            return redirect(url_for("dashboard"))

        user_id = user.get("id")
        if user_id in {room.get("host_user_id"), room.get("guest_user_id")} or is_admin_user(user):
            return redirect(url_for("room_detail", room_id=room_id))

        if room.get("status") != "waiting_ready":
            flash("Phòng đã bắt đầu hoặc không còn nhận người tham gia.", "warning")
            return redirect(url_for("dashboard"))

        if room.get("guest_user_id"):
            flash("Phòng đã có đủ hai người chơi.", "warning")
            return redirect(url_for("dashboard"))

        if is_player_in_cooldown(user):
            flash(f"Bạn đang trong thời gian chờ {cooldown_text(user)}.", "warning")
            return redirect(url_for("dashboard"))

        existing_room = active_room_for_user(user_id)
        if existing_room:
            flash("Bạn đang có một phòng chưa hoàn tất. Hãy xử lý phòng đó trước.", "warning")
            return redirect(url_for("room_detail", room_id=existing_room.get("id")))

        if active_match_for_user(user_id):
            flash("Bạn đang có trận chưa hoàn tất nên chưa thể vào phòng khác.", "warning")
            return redirect(url_for("dashboard"))

        host_id = room.get("host_user_id")
        host_other_room = active_room_for_user(host_id, exclude_room_id=room_id)
        if active_match_for_user(host_id) or host_other_room:
            flash("Chủ phòng đang ở một phòng hoặc trận khác. Link này không còn hiệu lực.", "warning")
            return redirect(url_for("dashboard"))

        joined_at = now_iso()
        update_result = execute_query(
            db.table("match_rooms").update({
                "invite_id": None,
                "guest_user_id": user_id,
                "guest_ready": False,
                "guest_team": None,
                "guest_team_overall": None,
                "guest_team_logo_url": None,
                "guest_team_league": None,
                "note": f'{user.get("display_name") or user.get("username") or "Người chơi"} đã tham gia qua link chia sẻ. Khách chưa sẵn sàng.',
                "state_expires_at": None,
                "updated_at": joined_at,
            })
            .eq("id", room_id)
            .eq("status", "waiting_ready")
            .is_("guest_user_id", "null"),
            "join_shared_room",
            attempts=3,
        )

        joined_rows = update_result.data or []
        if not joined_rows:
            latest_room = get_room(room_id)
            if latest_room and latest_room.get("guest_user_id") == user_id:
                return redirect(url_for("room_detail", room_id=room_id))
            flash("Có người khác vừa tham gia trước bạn hoặc phòng đã thay đổi trạng thái.", "warning")
            return redirect(url_for("dashboard"))

        # Link chia sẻ có thể được dùng khi chủ phòng từng gửi lời mời riêng.
        # Hủy lời mời đang treo để người được mời cũ không thể nhận chỗ lần nữa.
        old_invite_id = room.get("invite_id")
        if old_invite_id:
            try:
                execute_query(
                    db.table("match_invites").update({
                        "status": "cancelled",
                        "updated_at": joined_at,
                    }).eq("id", old_invite_id).eq("status", "pending"),
                    "cancel_invite_after_shared_join",
                    attempts=2,
                )
            except Exception as exc:
                app.logger.warning("Shared room stale invite cleanup failed invite=%s: %s", old_invite_id, exc)

        cache_delete("_rz_rooms_all")
        cache_delete("_rz_invites_all")
        cache_delete("_rz_current_pending_invites")
        ttl_cache_delete("rooms_raw")
        ttl_cache_delete("invites_raw")

        flash("Bạn đã tham gia phòng qua link chia sẻ. Hãy bấm Sẵn Sàng khi đã chuẩn bị xong.", "success")
        return redirect(url_for("room_detail", room_id=room_id))


    @app.route("/room/<room_id>")
    @login_required

    def room_detail(room_id):
        user = current_user()

        try:
            room = get_room(room_id)
        except Exception:
            flash("Phòng đang tải chậm hoặc Supabase vừa ngắt kết nối. Vui lòng thử lại sau vài giây.", "warning")
            return redirect(url_for("rooms"))

        if not room:
            flash("Không tìm thấy phòng.", "danger")
            return redirect(url_for("rooms"))

        if user["id"] not in [room["host_user_id"], room["guest_user_id"]] and not is_admin_user(user):
            flash("Bạn không thuộc phòng này.", "danger")
            return redirect(url_for("rooms"))

        room_head_to_head = build_room_head_to_head(room)
        state_key = build_room_state_key(room)
        is_partial_request = request.headers.get("X-PES-Room-Partial") == "1"
        partial_flashes = get_flashed_messages(with_categories=True) if is_partial_request else []
        page_html = render_template(
            "room_detail.html",
            room=room,
            initial_room_state_key=state_key,
            friendly_tiers=get_available_team_tiers(),
            room_head_to_head=room_head_to_head,
        )

        if is_partial_request:
            begin_marker = "<!-- ROOM_LIVE_PARTIAL_BEGIN -->"
            end_marker = "<!-- ROOM_LIVE_PARTIAL_END -->"
            begin_at = page_html.find(begin_marker)
            end_at = page_html.find(end_marker)
            if begin_at >= 0 and end_at > begin_at:
                partial_html = page_html[begin_at + len(begin_marker):end_at].strip()
            else:
                app.logger.warning("Room partial markers missing room=%s", room_id)
                partial_html = page_html

            flash_payload = None
            if partial_flashes:
                category, message = partial_flashes[-1]
                flash_payload = {
                    "tone": "danger" if category == "danger" else ("success" if category == "success" else "warning"),
                    "message": str(message or "").strip(),
                }

            response = jsonify({
                "ok": True,
                "state_key": state_key,
                "status": room.get("status"),
                "html": partial_html,
                "flash": flash_payload,
            })
            response.headers["Cache-Control"] = "private, no-store, max-age=0"
            response.headers["X-Room-State-Key"] = state_key
            return response

        return page_html


    @app.route("/room/<room_id>/leave", methods=["POST"])
    @login_required
    def room_leave(room_id):
        user = current_user()
        room = get_room(room_id)

        if not room:
            flash("Không tìm thấy phòng.", "danger")
            return redirect(url_for("dashboard"))

        if user["id"] not in [room.get("host_user_id"), room.get("guest_user_id")]:
            flash("Bạn không thuộc phòng này.", "danger")
            return redirect(url_for("dashboard"))

        if room.get("status") not in {"waiting_ready", "friendly_playing"}:
            flash("Không thể rời phòng khi trận xếp hạng đang thi đấu hoặc đang chờ xác nhận kết quả.", "warning")
            return redirect(url_for("room_detail", room_id=room_id))

        # Ở bước chờ Sẵn Sàng, luồng rời phòng không phạt chỉ hợp lệ khi khách
        # chưa Sẵn Sàng. Kiểm tra tại backend để không thể né phạt bằng POST
        # trực tiếp vào endpoint /leave hoặc do giao diện vừa bị thay đổi trạng thái.
        if room.get("status") == "waiting_ready" and bool(room.get("guest_ready")):
            if user["id"] == room.get("guest_user_id"):
                flash("Bạn đã Sẵn Sàng. Thoát lúc này được tính là bỏ cuộc và trừ 20 RP.", "warning")
            else:
                flash("Khách đã Sẵn Sàng. Chủ phòng thoát lúc này được tính là bỏ cuộc và trừ 20 RP.", "warning")
            return redirect(url_for("room_detail", room_id=room_id))

        if user["id"] == room.get("guest_user_id"):
            execute_query(
                db.table("match_rooms").update({
                    "guest_user_id": None,
                    "guest_ready": False,
                    "guest_team": None,
                    "guest_team_overall": None,
                    "guest_team_logo_url": None,
                    "host_team": None,
                    "host_team_overall": None,
                    "host_team_logo_url": None,
                    "host_team_league": None,
                    "guest_team_league": None,
                    "status": "waiting_ready",
                    "match_id": None,
                    "invite_id": None,
                    "note": f'{user["display_name"]} đã rời phòng. Chủ phòng có thể mời đối thủ khác.',
                    "state_expires_at": None,
                    "updated_at": now_iso(),
                }).eq("id", room_id),
                "guest_leave_keep_room",
            )
            flash("Bạn đã rời phòng. Phòng vẫn được giữ cho chủ phòng và không ảnh hưởng điểm rank.", "success")
            return redirect(url_for("dashboard"))

        execute_query(
            db.table("match_rooms").update({
                "status": "cancelled",
                "guest_ready": False,
                "note": f'{user["display_name"]} đã đóng phòng.',
                "state_expires_at": None,
                "updated_at": now_iso(),
            }).eq("id", room_id),
            "host_close_room",
        )
        flash("Bạn đã thoát và đóng phòng đấu.", "success")
        return redirect(url_for("dashboard"))

