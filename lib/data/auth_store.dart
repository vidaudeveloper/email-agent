import 'package:flutter_secure_storage/flutter_secure_storage.dart';

class AuthSession {
  const AuthSession({
    required this.userId,
    required this.accessToken,
    this.refreshToken,
  });

  final String userId;
  final String accessToken;
  final String? refreshToken;
}

class AuthStore {
  AuthStore({FlutterSecureStorage? storage})
      : _storage = storage ?? const FlutterSecureStorage();

  final FlutterSecureStorage _storage;

  static const _kUserId = 'user_id';
  static const _kAccess = 'access_token';
  static const _kRefresh = 'refresh_token';

  Future<AuthSession?> read() async {
    final userId = await _storage.read(key: _kUserId);
    final access = await _storage.read(key: _kAccess);
    if (userId == null || access == null) return null;
    final refresh = await _storage.read(key: _kRefresh);
    return AuthSession(
      userId: userId,
      accessToken: access,
      refreshToken: refresh,
    );
  }

  Future<void> save(AuthSession session) async {
    await _storage.write(key: _kUserId, value: session.userId);
    await _storage.write(key: _kAccess, value: session.accessToken);
    if (session.refreshToken != null) {
      await _storage.write(key: _kRefresh, value: session.refreshToken);
    }
  }

  Future<void> clear() async {
    await _storage.delete(key: _kUserId);
    await _storage.delete(key: _kAccess);
    await _storage.delete(key: _kRefresh);
  }
}
