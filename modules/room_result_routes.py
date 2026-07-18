"""Route nhập, xác nhận, tranh chấp và rút tranh chấp kết quả phòng đấu.

Module đăng ký route theo dependency của app.py để giữ nguyên endpoint và tránh import vòng.
"""

def register_routes(context):
    """Đăng ký nhóm route vào Flask app hiện tại."""
    globals().update(context)

    @app.route("/room/<room_id>/submit-result", methods=["POST"])
    @login_required
    def room_submit_result(room_id):
        user = current_user()
        room = get_room(room_id)

        if not room:
            flash("Không tìm thấy phòng.", "danger")
            return redirect(url_for("rooms"))

        if user["id"] != room["host_user_id"] and not is_admin_user(user):
            flash("Chỉ chủ phòng mới được nhập kết quả.", "danger")
            return redirect(url_for("room_detail", room_id=room_id))

        if room["status"] != "playing":
            flash("Chỉ trận đang đá mới được nhập kết quả.", "warning")
            return redirect(url_for("room_detail", room_id=room_id))

        try:
            assert_ranking_rebuild_not_running()
        except ValueError as exc:
            flash(str(exc), "warning")
            return redirect(url_for("room_detail", room_id=room_id))

        try:
            host_score = int(request.form.get("host_score", "0"))
            guest_score = int(request.form.get("guest_score", "0"))
        except (TypeError, ValueError):
            flash("Tỉ số phải là số nguyên.", "danger")
            return redirect(url_for("room_detail", room_id=room_id))

        if host_score < 0 or guest_score < 0:
            flash("Tỉ số không được âm.", "danger")
            return redirect(url_for("room_detail", room_id=room_id))

        match = get_match(room["match_id"])
        if not match:
            flash("Không tìm thấy match gắn với phòng.", "danger")
            return redirect(url_for("room_detail", room_id=room_id))

        if host_score > guest_score:
            winner_id = room["host_user_id"]
            loser_id = room["guest_user_id"]
        elif host_score < guest_score:
            winner_id = room["guest_user_id"]
            loser_id = room["host_user_id"]
        else:
            winner_id = None
            loser_id = None

        try:
            saved_match = execute_query(
                db.table("matches").update({
                    "score1": host_score,
                    "score2": guest_score,
                    "submitted_by_id": user["id"],
                    "winner_id": winner_id,
                    "loser_id": loser_id,
                    "status": "waiting_confirm",
                    "updated_at": now_iso(),
                }).eq("id", match["id"]).eq("status", "playing"),
                "submit_room_match_result",
            )
            if not (saved_match.data or []):
                raise ValueError("Trạng thái trận vừa thay đổi; kết quả chưa được lưu.")
            execute_query(
                db.table("match_rooms").update({
                    "host_score": host_score,
                    "guest_score": guest_score,
                    "submitted_by_id": user["id"],
                    "status": "waiting_result_confirm",
                    "state_expires_at": future_iso(RESULT_CONFIRM_TIMEOUT_SECONDS),
                    "updated_at": now_iso(),
                }).eq("id", room_id).eq("status", "playing"),
                "submit_room_result_state",
            )
            ttl_cache_delete("rooms_raw")
        except ValueError as exc:
            print(f"room_submit_result validation room={room_id} match={match.get('id')}: {exc}")
            flash(str(exc), "warning")
            return redirect(url_for("room_detail", room_id=room_id))
        except Exception as exc:
            print(f"room_submit_result ERROR room={room_id} match={match.get('id')}: {type(exc).__name__}: {exc}")
            flash("Không thể lưu kết quả do lỗi dữ liệu/kết nối. Vui lòng thử lại; chưa cộng hoặc trừ RP.", "danger")
            return redirect(url_for("room_detail", room_id=room_id))

        flash("Đã nhập kết quả. Đang chờ người được mời xác nhận.", "success")
        return redirect(url_for("room_detail", room_id=room_id))


    @app.route("/room/<room_id>/confirm-result", methods=["POST"])
    @login_required
    def room_confirm_result(room_id):
        user = current_user()
        room = get_room(room_id)

        if not room:
            flash("Không tìm thấy phòng.", "danger")
            return redirect(url_for("rooms"))

        if user["id"] != room["guest_user_id"] and not is_admin_user(user):
            flash("Chỉ người được mời mới được xác nhận kết quả.", "danger")
            return redirect(url_for("room_detail", room_id=room_id))

        if room["status"] != "waiting_result_confirm":
            flash("Phòng chưa có kết quả cần xác nhận.", "warning")
            return redirect(url_for("room_detail", room_id=room_id))

        match = get_match(room["match_id"])
        if not match:
            flash("Không tìm thấy trận.", "danger")
            return redirect(url_for("room_detail", room_id=room_id))

        try:
            users_before_streak_event = users_map()
            delta1, delta2 = apply_match_result(match)
            streak_event = build_win_streak_event(match, room, users_before_streak_event)
            execute_query(
                db.table("match_rooms").update({
                    "status": "confirmed",
                    "confirmed_by_id": user["id"],
                    "note": encode_win_streak_room_note(streak_event),
                    "state_expires_at": None,
                    "updated_at": now_iso(),
                }).eq("id", room_id).eq("status", "waiting_result_confirm"),
                "confirm_result_room",
            )
            if streak_event:
                publish_global_streak_event(streak_event)
        except ValueError as exc:
            print(f"room_confirm_result validation room={room_id} match={match.get('id')}: {exc}")
            flash(str(exc), "warning")
            return redirect(url_for("room_detail", room_id=room_id))
        except Exception as exc:
            print(f"room_confirm_result ERROR room={room_id} match={match.get('id')}: {type(exc).__name__}: {exc}")
            flash("Không thể xác nhận kết quả do lỗi kết nối dữ liệu. Điểm chưa được xử lý thêm; vui lòng thử lại sau vài giây.", "danger")
            return redirect(url_for("room_detail", room_id=room_id))

        return redirect(url_for("room_detail", room_id=room_id))


    @app.route("/room/<room_id>/dispute-result", methods=["POST"])
    @login_required
    def room_dispute_result(room_id):
        user = current_user()
        room = get_room(room_id)

        if not room:
            flash("Không tìm thấy phòng.", "danger")
            return redirect(url_for("rooms"))

        if user["id"] != room["guest_user_id"]:
            flash("Chỉ người được mời mới được báo tranh chấp.", "danger")
            return redirect(url_for("room_detail", room_id=room_id))

        if room["status"] != "waiting_result_confirm":
            flash("Phòng chưa có kết quả cần xác nhận.", "warning")
            return redirect(url_for("room_detail", room_id=room_id))

        try:
            assert_ranking_rebuild_not_running()
        except ValueError as exc:
            flash(str(exc), "warning")
            return redirect(url_for("room_detail", room_id=room_id))

        reason_code = request.form.get("reason_code", "").strip()
        details = request.form.get("details", "").strip()[:500]
        if reason_code not in {"wrong_score", "wrong_winner", "interrupted", "unilateral_entry", "other"}:
            flash("Hãy chọn lý do tranh chấp hợp lệ.", "danger")
            return redirect(url_for("room_detail", room_id=room_id))
        if reason_code == "other" and not details:
            flash("Hãy nhập ghi chú cho lý do khác.", "danger")
            return redirect(url_for("room_detail", room_id=room_id))

        evidence_path = None
        evidence_file = request.files.get("evidence")
        if evidence_file and getattr(evidence_file, "filename", ""):
            try:
                evidence_bytes = prepare_dispute_evidence_bytes(evidence_file)
                evidence_path = upload_dispute_evidence(room.get("match_id"), user.get("id"), evidence_bytes)
            except ValueError as exc:
                flash(str(exc), "danger")
                return redirect(url_for("room_detail", room_id=room_id))
            except Exception as exc:
                print(f"room_dispute_evidence upload error: {exc}")
                flash("Không thể tải ảnh bằng chứng lúc này. Vui lòng thử lại hoặc gửi tranh chấp không kèm ảnh.", "danger")
                return redirect(url_for("room_detail", room_id=room_id))

        reason_label = dispute_reason_label(reason_code)
        note = f"{user.get('display_name', 'Khách')} không đồng ý kết quả: {reason_label}."
        try:
            execute_query(
                db.table("match_rooms").update({
                    "status": "disputed",
                    "note": note,
                    "state_expires_at": None,
                    "updated_at": now_iso(),
                }).eq("id", room_id),
                "room_dispute_update",
            )

            if room.get("match_id"):
                execute_query(
                    db.table("matches").update({
                        "status": "disputed",
                        "note": note,
                        "updated_at": now_iso(),
                    }).eq("id", room["match_id"]),
                    "match_dispute_update",
                )

            dispute = create_or_update_match_dispute(
                room,
                user["id"],
                reason_code,
                details,
                "player",
                evidence_path=evidence_path,
            )
        except Exception as exc:
            if evidence_path:
                remove_dispute_evidence_object(evidence_path)
            try:
                execute_query(
                    db.table("match_rooms").update({
                        "status": "waiting_result_confirm",
                        "state_expires_at": future_iso(RESULT_CONFIRM_TIMEOUT_SECONDS),
                        "updated_at": now_iso(),
                    }).eq("id", room_id),
                    "rollback_room_dispute",
                    attempts=1,
                )
                if room.get("match_id"):
                    execute_query(
                        db.table("matches").update({
                            "status": "waiting_confirm",
                            "updated_at": now_iso(),
                        }).eq("id", room.get("match_id")),
                        "rollback_match_dispute",
                        attempts=1,
                    )
            except Exception as rollback_exc:
                print(f"room_dispute rollback warning: {rollback_exc}")
            print(f"room_dispute create error: {exc}")
            flash("Không thể gửi tranh chấp lúc này. Vui lòng thử lại sau vài giây.", "danger")
            return redirect(url_for("room_detail", room_id=room_id))
        notify_admins(
            "⚠️ Có tranh chấp kết quả mới",
            f"{room.get('host_name')} {room.get('host_score')} - {room.get('guest_score')} {room.get('guest_name')} • {reason_label}",
        )
        create_user_notification(
            room.get("host_user_id"),
            "⚠️ Đối thủ đã mở tranh chấp",
            f"{room.get('guest_name')} không đồng ý kết quả. Lý do: {reason_label}.",
            f"/room/{room_id}",
            "dispute",
        )

        flash("Đã gửi tranh chấp. Trận chưa được tính điểm và cả hai có thể về sảnh trong khi Admin xử lý.", "warning")
        return redirect(url_for("room_detail", room_id=room_id))


    @app.route("/room/<room_id>/withdraw-dispute", methods=["POST"])
    @login_required
    def room_withdraw_dispute(room_id):
        user = current_user()
        room = get_room(room_id)
        if not room or room.get("status") != "disputed":
            flash("Phòng không còn tranh chấp cần rút.", "warning")
            return redirect(url_for("dashboard"))

        dispute = get_match_dispute_by_match(room.get("match_id"), DISPUTE_PENDING_STATUSES)
        if not dispute or dispute.get("raised_by_id") != user.get("id"):
            flash("Chỉ người đã gửi tranh chấp mới có thể rút tranh chấp.", "danger")
            return redirect(url_for("room_detail", room_id=room_id))

        try:
            resolve_match_dispute_with_result(
                dispute,
                room.get("host_score"),
                room.get("guest_score"),
                user.get("id"),
                "accepted_by_player",
                "Người gửi đã rút tranh chấp và chấp nhận kết quả ban đầu.",
                final_dispute_status="withdrawn",
            )
        except Exception as exc:
            flash(f"Không thể rút tranh chấp: {exc}", "danger")
            return redirect(url_for("room_detail", room_id=room_id))

        flash("Đã rút tranh chấp và chấp nhận kết quả. Điểm rank đã được cập nhật.", "success")
        return redirect(url_for("room_detail", room_id=room_id))

