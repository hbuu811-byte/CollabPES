"""Route quay đội, quay lại giao hữu, kết thúc giao hữu và trạng thái sẵn sàng.

Module đăng ký route theo dependency của app.py để giữ nguyên endpoint và tránh import vòng.
"""

def register_routes(context):
    """Đăng ký nhóm route vào Flask app hiện tại."""
    globals().update(context)

    @app.route("/room/<room_id>/random-teams", methods=["POST"])
    @login_required
    def room_random_teams(room_id):
        user = current_user()
        room = get_room(room_id)

        if not room:
            flash("Không tìm thấy phòng.", "danger")
            return redirect(url_for("rooms"))
        if user["id"] != room["host_user_id"] and not is_admin_user(user):
            flash("Chỉ chủ phòng mới được quay đội.", "danger")
            return redirect(url_for("room_detail", room_id=room_id))
        if room["status"] != "waiting_ready":
            flash("Phòng không còn ở bước chờ quay đội.", "warning")
            return redirect(url_for("room_detail", room_id=room_id))
        if not room.get("guest_user_id"):
            flash("Phòng chưa có đối thủ. Hãy mời một người chơi vào phòng.", "warning")
            return redirect(url_for("room_detail", room_id=room_id))
        if not room.get("guest_ready"):
            flash("Đội khách chưa sẵn sàng. Hãy chờ khách bấm Sẵn sàng.", "warning")
            return redirect(url_for("room_detail", room_id=room_id))
        if room.get("match_id") or room.get("host_team") or room.get("guest_team"):
            flash("Phòng đã được quay đội hoặc đã tạo trận.", "warning")
            return redirect(url_for("room_detail", room_id=room_id))

        match_mode = (request.form.get("match_mode") or MATCH_MODE_RANKED).strip().lower()
        if match_mode == MATCH_MODE_FRIENDLY and not system_feature_enabled("friendly_enabled"):
            flash("Tính năng Giao hữu đang tạm tắt.", "warning")
            return redirect(url_for("room_detail", room_id=room_id))
        if match_mode not in {MATCH_MODE_RANKED, MATCH_MODE_FRIENDLY}:
            match_mode = MATCH_MODE_RANKED

        host = get_user(room["host_user_id"])
        guest = get_user(room["guest_user_id"])
        if not host or not guest:
            flash("Không tải được thông tin hai người chơi.", "danger")
            return redirect(url_for("room_detail", room_id=room_id))

        try:
            if match_mode == MATCH_MODE_FRIENDLY:
                selected_tier = (request.form.get("friendly_tier") or room.get("friendly_tier") or "A").strip().upper()
                result = friendly_random_team_pair(selected_tier)
                execute_query(
                    db.table("match_rooms").update({
                        "host_team": result["team_a"],
                        "guest_team": result["team_b"],
                        "host_team_overall": result["overall_a"],
                        "guest_team_overall": result["overall_b"],
                        "host_team_logo_url": result.get("logo_a") or None,
                        "guest_team_logo_url": result.get("logo_b") or None,
                        "host_team_league": result.get("league_a") or None,
                        "guest_team_league": result.get("league_b") or None,
                        "team_tier": selected_tier,
                        "friendly_tier": selected_tier,
                        "match_mode": MATCH_MODE_FRIENDLY,
                        "status": "friendly_playing",
                        "match_id": None,
                        "note": f"Giao hữu Tier {selected_tier}; không lưu lịch sử và không tính RP.",
                        "state_expires_at": None,
                        "updated_at": now_iso(),
                    }).eq("id", room_id).eq("status", "waiting_ready"),
                    "room_friendly_random",
                )
                flash(
                    f'Giao hữu Tier {selected_tier}: {result["team_a"]} ({result.get("league_a") or "Không rõ giải"}) vs '
                    f'{result["team_b"]} ({result.get("league_b") or "Không rõ giải"}). Không lưu lịch sử, không tính điểm.',
                    "success",
                )
                return redirect(url_for("room_detail", room_id=room_id))

            result = smart_random_team_pair(host, guest)
            match_result = execute_query(
                db.table("matches").insert({
                    "player1_id": room["host_user_id"],
                    "player2_id": room["guest_user_id"],
                    "team1": result["team_a"],
                    "team2": result["team_b"],
                    "team1_overall": result["overall_a"],
                    "team2_overall": result["overall_b"],
                    "team1_logo_url": result.get("logo_a") or None,
                    "team2_logo_url": result.get("logo_b") or None,
                    "team1_league": result.get("league_a") or None,
                    "team2_league": result.get("league_b") or None,
                    "host_xp_factor": HOST_XP_FACTOR,
                    "status": "playing",
                    "note": "",
                    "updated_at": now_iso(),
                }),
                "room_random_create_match",
            )
            match = match_result.data[0] if match_result.data else None
            if not match:
                flash("Không thể tạo trận sau khi quay đội. Vui lòng thử lại.", "danger")
                return redirect(url_for("room_detail", room_id=room_id))

            execute_query(
                db.table("match_rooms").update({
                    "host_team": result["team_a"],
                    "guest_team": result["team_b"],
                    "host_team_overall": result["overall_a"],
                    "guest_team_overall": result["overall_b"],
                    "host_team_logo_url": result.get("logo_a") or None,
                    "guest_team_logo_url": result.get("logo_b") or None,
                    "host_team_league": result.get("league_a") or None,
                    "guest_team_league": result.get("league_b") or None,
                    "team_tier": SMART_RANDOM_MODE,
                    "match_mode": MATCH_MODE_RANKED,
                    "status": "playing",
                    "match_id": match["id"],
                    "state_expires_at": None,
                    "updated_at": now_iso(),
                }).eq("id", room_id).eq("status", "waiting_ready"),
                "room_random_start_match",
            )
        except ValueError as exc:
            flash(str(exc), "warning")
            return redirect(url_for("room_detail", room_id=room_id))

        return redirect(url_for("room_detail", room_id=room_id))


    @app.route("/room/<room_id>/reroll-friendly", methods=["POST"])
    @login_required
    def room_reroll_friendly(room_id):
        if not system_feature_enabled("friendly_enabled"):
            flash("Tính năng Giao hữu đang tạm tắt.", "warning")
            return redirect(url_for("room_detail", room_id=room_id))
        user = current_user()
        room = get_room(room_id)
        if not room:
            flash("Không tìm thấy phòng.", "danger")
            return redirect(url_for("dashboard"))
        if user["id"] != room.get("host_user_id") and not is_admin_user(user):
            flash("Chỉ chủ phòng mới được quay lại đội giao hữu.", "danger")
            return redirect(url_for("room_detail", room_id=room_id))
        if room.get("status") != "friendly_playing":
            flash("Phòng không có trận giao hữu đang diễn ra.", "warning")
            return redirect(url_for("room_detail", room_id=room_id))

        selected_tier = (room.get("friendly_tier") or "A").strip().upper()
        try:
            result = friendly_random_team_pair(
                selected_tier,
                excluded_names=[room.get("host_team"), room.get("guest_team")],
            )
        except ValueError as exc:
            flash(str(exc), "warning")
            return redirect(url_for("room_detail", room_id=room_id))

        execute_query(
            db.table("match_rooms").update({
                "host_team": result["team_a"],
                "guest_team": result["team_b"],
                "host_team_overall": result["overall_a"],
                "guest_team_overall": result["overall_b"],
                "host_team_logo_url": result.get("logo_a") or None,
                "guest_team_logo_url": result.get("logo_b") or None,
                "host_team_league": result.get("league_a") or None,
                "guest_team_league": result.get("league_b") or None,
                "note": f"Đã quay lại đội giao hữu Tier {selected_tier}.",
                "updated_at": now_iso(),
            }).eq("id", room_id).eq("status", "friendly_playing"),
            "reroll_friendly_match",
        )
        flash("Đã tự random tiếp hai CLB giao hữu.", "success")
        return redirect(url_for("room_detail", room_id=room_id))


    @app.route("/room/<room_id>/finish-friendly", methods=["POST"])
    @login_required
    def room_finish_friendly(room_id):
        if not system_feature_enabled("friendly_enabled"):
            flash("Tính năng Giao hữu đang tạm tắt.", "warning")
            return redirect(url_for("room_detail", room_id=room_id))
        user = current_user()
        room = get_room(room_id)
        if not room:
            flash("Không tìm thấy phòng.", "danger")
            return redirect(url_for("dashboard"))
        if user["id"] not in [room.get("host_user_id"), room.get("guest_user_id")] and not is_admin_user(user):
            flash("Bạn không thuộc phòng này.", "danger")
            return redirect(url_for("dashboard"))
        if room.get("status") != "friendly_playing":
            flash("Phòng không có trận giao hữu đang diễn ra.", "warning")
            return redirect(url_for("room_detail", room_id=room_id))
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
                "guest_ready": bool(room.get("guest_user_id")),
                "status": "waiting_ready",
                "match_id": None,
                "note": "Trận giao hữu đã kết thúc. Đang chờ Chủ Phòng quay đội tiếp theo.",
                "updated_at": now_iso(),
            }).eq("id", room_id).eq("status", "friendly_playing"),
            "finish_friendly_match",
        )
        flash("Đã kết thúc giao hữu. Không lưu lịch sử và không thay đổi RP.", "success")
        return redirect(url_for("room_detail", room_id=room_id))


    @app.route("/room/<room_id>/guest-unready", methods=["POST"])
    @login_required
    def room_guest_unready(room_id):
        user = current_user()
        room = get_room(room_id)
        if not room or user.get("id") != room.get("guest_user_id"):
            flash("Bạn không thuộc phòng đấu này.", "danger")
            return redirect(url_for("dashboard"))
        if room.get("status") != "waiting_ready":
            flash("Không thể hủy sẵn sàng ở trạng thái hiện tại.", "warning")
            return redirect(url_for("room_detail", room_id=room_id))
        execute_query(
            db.table("match_rooms").update({
                "guest_ready": False,
                "note": "Khách đã hủy sẵn sàng.",
            }).eq("id", room_id).eq("status", "waiting_ready"),
            "room_guest_unready",
        )
        cache_delete("_rz_rooms_all")
        ttl_cache_delete("rooms_raw")
        flash("Đã hủy trạng thái sẵn sàng.", "success")
        return redirect(url_for("room_detail", room_id=room_id))


    @app.route("/room/<room_id>/guest-ready", methods=["POST"])
    @login_required
    def room_guest_ready(room_id):
        user = current_user()
        room = get_room(room_id)
        if not room or user.get("id") != room.get("guest_user_id"):
            flash("Bạn không thuộc phòng đấu này.", "danger")
            return redirect(url_for("dashboard"))
        if room.get("status") != "waiting_ready":
            flash("Không thể đổi trạng thái sẵn sàng lúc này.", "warning")
            return redirect(url_for("room_detail", room_id=room_id))
        execute_query(
            db.table("match_rooms").update({
                "guest_ready": True,
                "note": "Khách đã sẵn sàng. Chủ phòng có thể quay đội.",
            }).eq("id", room_id).eq("status", "waiting_ready"),
            "room_guest_ready",
        )
        cache_delete("_rz_rooms_all")
        ttl_cache_delete("rooms_raw")
        flash("Bạn đã sẵn sàng.", "success")
        return redirect(url_for("room_detail", room_id=room_id))


    @app.route("/room/<room_id>/start", methods=["POST"])
    @login_required
    def room_start(room_id):
        # Giữ endpoint để tương thích với trang cũ đang được cache.
        flash("V1.10.0 đã bỏ nút Sẵn sàng và Bắt đầu trận. Chủ phòng chỉ cần quay đội.", "warning")
        return redirect(url_for("room_detail", room_id=room_id))

