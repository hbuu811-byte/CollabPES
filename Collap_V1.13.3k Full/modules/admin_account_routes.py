"""Route Admin tài khoản: tài khoản test, import CSV, duyệt/khóa tài khoản và phân quyền.

Module đăng ký route theo dependency của app.py để giữ nguyên endpoint và tránh import vòng.
"""

def register_routes(context):
    """Đăng ký nhóm route vào Flask app hiện tại."""
    globals().update(context)

    def _safe_bounded_int(value, default=0, minimum=0, maximum=999999):
        """Parse integers that must stay inside an explicit range."""
        try:
            parsed = int(str(value).strip())
        except (TypeError, ValueError):
            return int(default)
        return max(minimum, min(maximum, parsed))


    def _csv_password_value(row):
        """Đọc mật khẩu từ cột password hoặc pass; chuỗi trống nghĩa là không cung cấp."""
        value = row.get("password")
        if value is None or str(value).strip() == "":
            value = row.get("pass")
        return str(value or "").strip()


    def _build_test_user_payload(row, default_password="Test@12345"):
        username = str(row.get("username") or "").strip()
        display_name = str(row.get("display_name") or username).strip() or username
        supplied_password = _csv_password_value(row)
        password = supplied_password or default_password
        zalo_name = str(row.get("zalo_name") or "Tài khoản test").strip() or "Tài khoản test"
        if len(username) < 3 or len(username) > 30:
            raise ValueError("Tên tài khoản phải từ 3 đến 30 ký tự.")
        if len(password) < minimum_password_length():
            raise ValueError(f"Mật khẩu của {username} phải có ít nhất {minimum_password_length()} ký tự.")

        wins = _safe_bounded_int(row.get("wins"), 0)
        draws = _safe_bounded_int(row.get("draws"), 0)
        losses = _safe_bounded_int(row.get("losses"), 0)
        supplied_total = _safe_bounded_int(row.get("total_matches"), wins + draws + losses)
        total_matches = max(supplied_total, wins + draws + losses)

        return {
            "username": username,
            "password_hash": hash_password(password),
            "display_name": display_name[:80],
            "zalo_name": zalo_name[:80],
            "role": "player",
            "account_status": "approved",
            "invite_code_used": None,
            "rank_points": _safe_bounded_int(row.get("rank_points"), DEFAULT_POINTS, -999999, 999999),
            "wins": wins,
            "draws": draws,
            "losses": losses,
            "total_matches": total_matches,
            "goals_for": _safe_bounded_int(row.get("goals_for"), 0),
            "goals_against": _safe_bounded_int(row.get("goals_against"), 0),
            "is_online": False,
            "must_change_password": False,
            "register_ip": "ADMIN_TEST_IMPORT",
            "register_user_agent": "PES 2026 Admin Test Data",
        }


    @app.route("/admin/test-account/create", methods=["POST"])
    @login_required
    @admin_required
    @admin_permission_required("users_edit")
    def admin_create_test_account():
        row = {
            "username": request.form.get("username", ""),
            "display_name": request.form.get("display_name", ""),
            "password": request.form.get("password", ""),
            "zalo_name": request.form.get("zalo_name", "Tài khoản test"),
            "rank_points": request.form.get("rank_points", DEFAULT_POINTS),
        }
        try:
            payload = _build_test_user_payload(row)
            if get_user_by_username(payload["username"]):
                flash("Tên tài khoản test đã tồn tại.", "warning")
                return redirect_admin("test-data")
            execute_query(db.table("users").insert(payload), "admin_create_test_account")
            cache_delete("_rz_players_all")
            cache_delete("_rz_users_map")
            log_admin_action("create_test_account", "user", None, payload["username"], {"rank_points": payload["rank_points"]})
            flash(f"Đã tạo tài khoản test {payload['username']}.", "success")
        except Exception as exc:
            flash(f"Không thể tạo tài khoản test: {exc}", "danger")
        return redirect_admin("test-data")



    @app.route("/admin/test-account/sample.csv")
    @login_required
    @admin_required
    @admin_permission_required("accounts_import")
    def admin_download_test_account_sample():
        sample_rows = [
            ["username", "display_name", "password", "zalo_name", "rank_points", "wins", "draws", "losses", "total_matches", "goals_for", "goals_against", "register_ip", "last_ip"],
            ["test01", "Test Player 01", "123456", "Test 01", "1200", "5", "2", "3", "10", "12", "9", "", ""],
            ["test02", "Test Player 02", "123456", "Test 02", "-1000", "0", "0", "0", "0", "0", "0", "", ""],
        ]
        output = io.StringIO()
        writer = csv.writer(output, lineterminator="\n")
        writer.writerows(sample_rows)
        response = make_response("\ufeff" + output.getvalue())
        response.headers["Content-Type"] = "text/csv; charset=utf-8"
        response.headers["Content-Disposition"] = 'attachment; filename="PES_Arena_Import_Tai_Khoan_Mau_v1.13.2.csv"'
        response.headers["Cache-Control"] = "no-store"
        return response

    @app.route("/admin/test-account/import", methods=["POST"])
    @login_required
    @admin_required
    @admin_permission_required("accounts_import")
    def admin_import_test_accounts():
        upload = request.files.get("csv_file")
        pasted_csv = request.form.get("csv_text", "").strip()
        default_password = request.form.get("default_password", "Test@12345").strip() or "Test@12345"
        if len(default_password) < minimum_password_length():
            flash(f"Mật khẩu mặc định phải có ít nhất {minimum_password_length()} ký tự.", "danger")
            return redirect_admin("test-data")

        if upload and upload.filename:
            if not upload.filename.lower().endswith(".csv"):
                flash("Chỉ hỗ trợ file CSV.", "danger")
                return redirect_admin("test-data")
            raw = upload.read(1024 * 1024 + 1)
            if len(raw) > 1024 * 1024:
                flash("File CSV tối đa 1 MB.", "danger")
                return redirect_admin("test-data")
            try:
                text = raw.decode("utf-8-sig")
            except UnicodeDecodeError:
                flash("File CSV phải dùng mã hóa UTF-8.", "danger")
                return redirect_admin("test-data")
        else:
            text = pasted_csv

        if not text:
            flash("Hãy chọn file CSV hoặc dán dữ liệu CSV.", "warning")
            return redirect_admin("test-data")

        reader = csv.DictReader(io.StringIO(text))
        required = {"username"}
        normalized_headers = {str(h or "").strip() for h in (reader.fieldnames or [])}
        if not required.issubset(normalized_headers):
            flash("CSV bắt buộc có cột username.", "danger")
            return redirect_admin("test-data")

        created, updated, errors = 0, 0, []
        seen_usernames = set()
        additive_fields = (
            "rank_points",
            "wins",
            "draws",
            "losses",
            "total_matches",
            "goals_for",
            "goals_against",
        )

        for line_no, raw_row in enumerate(reader, start=2):
            if line_no > 502:
                errors.append("Chỉ nhập tối đa 500 tài khoản mỗi lần.")
                break
            row = {str(k or "").strip(): (v or "").strip() for k, v in raw_row.items()}
            username = row.get("username", "").strip()
            if not username:
                continue

            username_key = username.lower()
            if username_key in seen_usernames:
                errors.append(f"Dòng {line_no}: username {username} bị lặp trong cùng file CSV nên không được cộng lần hai.")
                if len(errors) >= 8:
                    errors.append("Đã dừng hiển thị thêm lỗi.")
                    break
                continue
            seen_usernames.add(username_key)

            try:
                existing_user = get_user_by_username(username)
                if not existing_user:
                    payload = _build_test_user_payload(row, default_password)
                    execute_query(db.table("users").insert(payload), "admin_import_test_account")
                    created += 1
                    continue

                increments = {}
                for field in additive_fields:
                    raw_value = row.get(field, "")
                    if raw_value == "":
                        continue
                    # Chỉ rank_points được phép nhập số âm để Admin hoàn tác/trừ RP.
                    # Các thống kê trận đấu vẫn bắt buộc không âm để tránh dữ liệu sai.
                    if field == "rank_points":
                        increments[field] = _safe_bounded_int(raw_value, 0, -999999, 999999)
                    else:
                        increments[field] = _safe_bounded_int(raw_value, 0, 0, 999999)

                # Nếu CSV có thắng/hòa/thua nhưng không có total_matches,
                # tự cộng tổng số trận tương ứng để dữ liệu không bị lệch.
                if row.get("total_matches", "") == "":
                    wdl_increment = sum(increments.get(field, 0) for field in ("wins", "draws", "losses"))
                    if wdl_increment:
                        increments["total_matches"] = wdl_increment

                if not increments:
                    errors.append(f"Dòng {line_no}: tài khoản {username} đã tồn tại nhưng không có chỉ số nào để cộng.")
                    if len(errors) >= 8:
                        errors.append("Đã dừng hiển thị thêm lỗi.")
                        break
                    continue

                update_payload = {}
                for field, increment in increments.items():
                    current_value = _safe_bounded_int(existing_user.get(field), 0, 0, 999999)
                    if field == "rank_points":
                        # Cho phép cộng/trừ RP nhưng không để tổng điểm xuống dưới 0.
                        update_payload[field] = max(0, min(999999, current_value + increment))
                    else:
                        update_payload[field] = min(999999, current_value + increment)

                # Với tài khoản đã tồn tại: cột password/pass để trống sẽ giữ nguyên mật khẩu cũ.
                # Chỉ cập nhật mật khẩu khi CSV thực sự cung cấp một giá trị hợp lệ.
                supplied_password = _csv_password_value(row)
                if supplied_password:
                    if len(supplied_password) < minimum_password_length():
                        raise ValueError(f"Mật khẩu mới của {username} phải có ít nhất {minimum_password_length()} ký tự.")
                    update_payload["password_hash"] = hash_password(supplied_password)
                    update_payload["must_change_password"] = False
                    update_payload["password_changed_at"] = now_iso()

                execute_query(
                    db.table("users").update(update_payload).eq("id", existing_user["id"]),
                    "admin_import_add_user_stats",
                )
                updated += 1
            except Exception as exc:
                errors.append(f"Dòng {line_no}: {exc}")
                if len(errors) >= 8:
                    errors.append("Đã dừng hiển thị thêm lỗi.")
                    break

        cache_delete("_rz_players_all")
        cache_delete("_rz_users_map")
        log_admin_action(
            "import_test_accounts_additive",
            "user",
            None,
            "CSV additive import",
            {"created": created, "updated": updated, "errors": len(errors)},
        )
        if created or updated:
            flash(
                f"Import cộng dồn hoàn tất: tạo mới {created} tài khoản, cộng dữ liệu cho {updated} tài khoản đã có.",
                "success",
            )
        else:
            flash("Không có tài khoản nào được tạo mới hoặc cộng dữ liệu.", "warning")
        for message in errors[:8]:
            flash(message, "danger")
        return redirect_admin("test-data")


    @app.route("/admin/password-reset/<request_id>/resolve", methods=["POST"])
    @login_required
    @admin_required
    @admin_permission_required("password_reset")
    def admin_resolve_password_reset(request_id):
        reset_request = get_password_reset_request(request_id)
        if not reset_request or reset_request.get("status") != "pending":
            flash("Yêu cầu khôi phục không còn hiệu lực.", "warning")
            return redirect_admin("passwords")

        user = get_user(reset_request.get("user_id"))
        temporary_password = request.form.get("temporary_password", "").strip()
        if not user:
            flash("Không tìm thấy tài khoản cần khôi phục.", "danger")
            return redirect_admin("passwords")
        if len(temporary_password) < minimum_password_length():
            flash(f"Mật khẩu tạm phải có ít nhất {minimum_password_length()} ký tự.", "danger")
            return redirect_admin("passwords")

        actor = current_user()
        execute_query(
            db.table("users").update({
                "password_hash": hash_password(temporary_password),
                "must_change_password": True,
                "password_changed_at": now_iso(),
            }).eq("id", user["id"]),
            "admin_issue_temporary_password",
        )
        execute_query(
            db.table("password_reset_requests").update({
                "status": "resolved",
                "admin_user_id": actor["id"],
                "admin_note": "Đã cấp mật khẩu tạm; không lưu mật khẩu gốc.",
                "resolved_at": now_iso(),
            }).eq("id", request_id),
            "resolve_password_reset_request",
        )
        log_admin_action(
            "Cấp mật khẩu tạm",
            "user",
            user.get("id"),
            user.get("username"),
            "User buộc phải đổi mật khẩu sau lần đăng nhập tiếp theo.",
        )
        flash(f"Đã cấp mật khẩu tạm cho {user.get('username')}. Hãy gửi mật khẩu này cho user qua Zalo; hệ thống không lưu lại mật khẩu tạm.", "success")
        return redirect_admin("passwords")


    @app.route("/admin/password-reset/<request_id>/reject", methods=["POST"])
    @login_required
    @admin_required
    @admin_permission_required("password_reset")
    def admin_reject_password_reset(request_id):
        reset_request = get_password_reset_request(request_id)
        if not reset_request or reset_request.get("status") != "pending":
            flash("Yêu cầu khôi phục không còn hiệu lực.", "warning")
            return redirect_admin("passwords")

        actor = current_user()
        note = request.form.get("note", "").strip()[:250]
        execute_query(
            db.table("password_reset_requests").update({
                "status": "rejected",
                "admin_user_id": actor["id"],
                "admin_note": note or "Admin từ chối yêu cầu.",
                "resolved_at": now_iso(),
            }).eq("id", request_id),
            "reject_password_reset_request",
        )
        log_admin_action(
            "Từ chối khôi phục mật khẩu",
            "user",
            reset_request.get("user_id"),
            reset_request.get("username_snapshot"),
            note or "Không có ghi chú.",
        )
        flash("Đã từ chối yêu cầu khôi phục mật khẩu.", "success")
        return redirect_admin("passwords")


    @app.route("/admin/account/<user_id>/approve", methods=["POST"])
    @login_required
    @admin_required
    @admin_permission_required("users_approve")
    def admin_approve_account(user_id):
        user = get_user(user_id)
        if not user or user.get("role") != "player":
            flash("Không tìm thấy tài khoản player.", "danger")
            return redirect_admin("overview")

        actor = current_user()
        execute_query(
            db.table("users").update({
                "account_status": "approved",
                "approved_by": actor["id"],
                "approved_at": now_iso(),
                "rejection_reason": None,
            }).eq("id", user_id),
            "approve_account",
        )
        log_admin_action("Duyệt tài khoản", "user", user_id, user.get("username"), "Trạng thái: approved")
        flash(f"Đã duyệt tài khoản {user.get('username')}.", "success")
        return redirect_admin("overview")


    @app.route("/admin/account/<user_id>/reject", methods=["POST"])
    @login_required
    @admin_required
    @admin_permission_required("users_approve")
    def admin_reject_account(user_id):
        user = get_user(user_id)
        if not user or user.get("role") != "player":
            flash("Không tìm thấy tài khoản player.", "danger")
            return redirect_admin("overview")

        reason = request.form.get("reason", "").strip()[:200]
        execute_query(
            db.table("users").update({
                "account_status": "rejected",
                "is_online": False,
                "rejection_reason": reason or "Admin từ chối tài khoản.",
            }).eq("id", user_id),
            "reject_account",
        )
        log_admin_action("Từ chối tài khoản", "user", user_id, user.get("username"), reason or "Không có lý do.")
        flash("Đã từ chối tài khoản.", "success")
        return redirect_admin("overview")


    @app.route("/admin/account/<user_id>/ban", methods=["POST"])
    @login_required
    @admin_required
    @admin_permission_required("users_edit")
    def admin_ban_account(user_id):
        user = get_user(user_id)
        actor = current_user()
        if not user or user.get("role") != "player":
            flash("Không tìm thấy tài khoản player.", "danger")
            return redirect_admin("users")
        if is_admin_user(user) and not is_owner_user(actor):
            flash("Chỉ chủ hệ thống mới có thể xử lý tài khoản Admin phụ.", "danger")
            return redirect_admin("users")
        if is_admin_user(user):
            flash("Hãy gỡ quyền Admin trước khi khóa tài khoản.", "danger")
            return redirect_admin("users")

        execute_query(
            db.table("users").update({"account_status": "banned", "is_online": False}).eq("id", user_id),
            "ban_account",
        )
        log_admin_action("Khóa tài khoản", "user", user_id, user.get("username"), "Trạng thái: banned")
        flash("Đã khóa tài khoản.", "success")
        return redirect_admin("users")

    @app.route("/admin/account/<user_id>/unban", methods=["POST"])
    @login_required
    @admin_required
    @admin_permission_required("users_edit")
    def admin_unban_account(user_id):
        user = get_user(user_id)
        if not user or user.get("role") != "player":
            flash("Không tìm thấy tài khoản player.", "danger")
            return redirect_admin("users")

        execute_query(
            db.table("users").update({"account_status": "approved"}).eq("id", user_id),
            "unban_account",
        )
        log_admin_action("Mở khóa tài khoản", "user", user_id, user.get("username"), "Trạng thái: approved")
        flash("Đã mở khóa tài khoản.", "success")
        return redirect_admin("users")


    @app.route("/admin/invite-code/create", methods=["POST"])
    @login_required
    @admin_required
    @admin_permission_required("registration_codes_manage")
    def admin_create_invite_code():
        actor = current_user()
        label = request.form.get("label", "").strip()[:80]

        for _ in range(10):
            code_value = generate_invite_code_value()
            if not get_invite_code_record(code_value):
                execute_query(
                    db.table("registration_invite_codes").insert({
                        "code": code_value,
                        "created_by": actor["id"],
                        "label": label,
                        "is_active": True,
                    }),
                    "create_invite_code",
                )
                log_admin_action("Tạo mã mời", "invite_code", target_label=code_value, details=label or "Không có nhãn.")
                flash(f"Đã tạo mã mời: {code_value}", "success")
                return redirect(url_for("admin"))

        flash("Không tạo được mã mời, vui lòng thử lại.", "danger")
        return redirect(url_for("admin"))


    @app.route("/admin/invite-code/<code_id>/disable", methods=["POST"])
    @login_required
    @admin_required
    @admin_permission_required("registration_codes_manage")
    def admin_disable_invite_code(code_id):
        execute_query(
            db.table("registration_invite_codes").update({"is_active": False}).eq("id", code_id),
            "disable_invite_code",
        )
        log_admin_action("Vô hiệu hóa mã mời", "invite_code", code_id)
        flash("Đã vô hiệu hóa mã mời.", "success")
        return redirect(url_for("admin"))


    @app.route("/admin/user/<user_id>/promote", methods=["POST"])
    @login_required
    @owner_required
    def admin_promote_user(user_id):
        user = get_user(user_id)
        if (
            not user
            or user.get("role") != "player"
            or user.get("account_status") != "approved"
            or user.get("admin_level", "none") != "none"
        ):
            flash("Chỉ có thể thêm player đã được duyệt làm admin.", "danger")
            return redirect_admin("users")

        execute_query(
            db.table("users").update({"admin_level": "admin", "admin_permissions": {}, "admin_can_create_test_account": False, "admin_can_import_accounts_csv": False}).eq("id", user_id),
            "promote_admin",
        )
        log_admin_action("Thêm Admin phụ", "user", user_id, user.get("username"), "admin_level: none → admin")
        flash(f"Đã thêm {user.get('username')} làm admin phụ. Người này vẫn có thể thi đấu.", "success")
        return redirect_admin("users")


    @app.route("/admin/user/<user_id>/permissions", methods=["POST"])
    @login_required
    @owner_required
    def admin_update_permissions(user_id):
        user = get_user(user_id)
        if not user or user.get("admin_level") != "admin":
            flash("Không tìm thấy Admin phụ.", "danger")
            return redirect_admin("overview")

        payload = {code: request.form.get(code) == "1" for codes in ADMIN_PERMISSION_GROUPS.values() for code in codes}
        db_payload = {
            "admin_permissions": payload,
            "admin_can_create_test_account": payload.get("users_edit", False),
            "admin_can_import_accounts_csv": payload.get("accounts_import", False),
        }
        try:
            execute_query(
                db.table("users").update(db_payload).eq("id", user_id),
                "update_admin_permissions",
            )
        except Exception as exc:
            error_text = str(exc)
            lowered = error_text.lower()
            missing_permission_columns = (
                "admin_can_create_test_account" in lowered
                or "admin_can_import_accounts_csv" in lowered
                or "pgrst204" in lowered
                or "column" in lowered and "schema cache" in lowered
            )
            app.logger.exception("Không thể lưu quyền Admin phụ")
            if missing_permission_columns:
                flash(
                    "Supabase chưa có cột quyền Admin phụ. Hãy chạy file "
                    "docs/update_admin_permissions_v1_9_1.sql trong Supabase SQL Editor rồi lưu lại.",
                    "danger",
                )
            else:
                flash(
                    "Không thể lưu quyền Admin phụ do lỗi kết nối dữ liệu. Vui lòng thử lại và kiểm tra Runtime Logs.",
                    "danger",
                )
            return redirect_admin("overview")

        cache_delete("_rz_players_all")
        cache_delete("_rz_users_map")
        log_admin_action("Cập nhật quyền Admin phụ", "user", user_id, user.get("username"), payload)
        flash(f"Đã cập nhật quyền cho Admin phụ {user.get('username')}.", "success")
        return redirect_admin("overview")

    @app.route("/admin/user/<user_id>/demote", methods=["POST"])
    @login_required
    @owner_required
    def admin_demote_user(user_id):
        user = get_user(user_id)
        if not user or user.get("admin_level") != "admin":
            flash("Không tìm thấy admin phụ.", "danger")
            return redirect_admin("users")

        execute_query(
            db.table("users").update({"admin_level": "none", "admin_permissions": {}, "admin_can_create_test_account": False, "admin_can_import_accounts_csv": False}).eq("id", user_id),
            "demote_admin",
        )
        log_admin_action("Gỡ Admin phụ", "user", user_id, user.get("username"), "admin_level: admin → none")
        flash("Đã gỡ quyền admin phụ.", "success")
        return redirect_admin("users")

