import 'package:flutter/material.dart';
import 'package:go_router/go_router.dart';

import 'core/theme.dart';
import 'features/auth/login_page.dart';
import 'features/chat/chat_page.dart';
import 'features/devices/devices_page.dart';
import 'state/auth_controller.dart';

class VidauApp extends StatelessWidget {
  const VidauApp({super.key, required this.router});

  final GoRouter router;

  @override
  Widget build(BuildContext context) {
    return MaterialApp.router(
      title: 'Vidau Mobile',
      theme: AppTheme.light(),
      routerConfig: router,
    );
  }
}

GoRouter buildRouter(AuthController auth) {
  return GoRouter(
    initialLocation: '/login',
    refreshListenable: auth,
    redirect: (context, state) {
      if (auth.loading) return null;
      final loggedIn = auth.session != null;
      final onLogin = state.matchedLocation == '/login';
      if (!loggedIn && !onLogin) return '/login';
      if (loggedIn && onLogin) return '/devices';
      return null;
    },
    routes: [
      GoRoute(path: '/login', builder: (context, state) => const LoginPage()),
      GoRoute(path: '/devices', builder: (context, state) => const DevicesPage()),
      GoRoute(
        path: '/chat/:deviceId',
        builder: (context, state) {
          final id = state.pathParameters['deviceId']!;
          final name = state.extra as String?;
          return ChatPage(deviceId: id, deviceName: name);
        },
      ),
    ],
  );
}
