import 'package:flutter/material.dart';
import 'package:provider/provider.dart';

import '../../core/config.dart';
import '../../state/auth_controller.dart';
import '../../widgets/link_mode_banner.dart';

class LoginPage extends StatelessWidget {
  const LoginPage({super.key});

  @override
  Widget build(BuildContext context) {
    final auth = context.watch<AuthController>();
    final config = context.watch<AppConfig>();
    return Scaffold(
      body: Column(
        crossAxisAlignment: CrossAxisAlignment.stretch,
        children: [
          const LinkModeBanner(),
          Expanded(
            child: SafeArea(
              top: false,
              child: Padding(
                padding: const EdgeInsets.all(24),
                child: Column(
                  crossAxisAlignment: CrossAxisAlignment.stretch,
                  children: [
                    const Spacer(),
                    Text(
                      'Vidau',
                      style: Theme.of(context).textTheme.displaySmall?.copyWith(
                            fontWeight: FontWeight.w700,
                          ),
                    ),
                    const SizedBox(height: 8),
                    Text(
                      '链接电脑，在手机上驱动桌面 Agent。',
                      style: Theme.of(context).textTheme.bodyLarge?.copyWith(
                            color: Theme.of(context).colorScheme.onSurfaceVariant,
                          ),
                    ),
                    const Spacer(),
                    if (auth.error != null) ...[
                      Text(
                        auth.error!,
                        style: TextStyle(color: Theme.of(context).colorScheme.error),
                      ),
                      const SizedBox(height: 12),
                    ],
                    FilledButton(
                      onPressed: auth.loading ? null : () => auth.signInDemo(),
                      child: auth.loading
                          ? const SizedBox(
                              height: 18,
                              width: 18,
                              child: CircularProgressIndicator(strokeWidth: 2),
                            )
                          : Text(
                              config.linkMode == LinkMode.remote
                                  ? '登录并连接 Gateway'
                                  : '使用演示账号继续（Mock）',
                            ),
                    ),
                    const SizedBox(height: 12),
                    Text(
                      config.linkMode == LinkMode.remote
                          ? '将请求 ${config.gatewayHttpBaseUrl}/auth/demo\n'
                              '真机请用: flutter run --dart-define=GATEWAY_HOST=<电脑局域网IP>'
                          : 'Mock 模式不会驱动真实桌面。',
                      textAlign: TextAlign.center,
                      style: Theme.of(context).textTheme.bodySmall?.copyWith(
                            color: Theme.of(context).colorScheme.onSurfaceVariant,
                          ),
                    ),
                  ],
                ),
              ),
            ),
          ),
        ],
      ),
    );
  }
}
