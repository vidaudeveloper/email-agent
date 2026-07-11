import 'package:flutter/material.dart';

import '../core/config.dart';

/// Visible mode chip so Mock vs Remote is never ambiguous.
class LinkModeBanner extends StatelessWidget {
  const LinkModeBanner({super.key});

  @override
  Widget build(BuildContext context) {
    final config = AppConfig.current;
    final isRemote = config.linkMode == LinkMode.remote;
    final bg = isRemote ? const Color(0xFF0B6E4F) : const Color(0xFF8A4B08);
    final label = isRemote
        ? 'Remote · ${config.gatewayHttpBaseUrl}'
        : 'Mock · 本地模拟（不会驱动真实桌面）';
    return ColoredBox(
      color: bg,
      child: SizedBox(
        width: double.infinity,
        child: Padding(
          padding: const EdgeInsets.symmetric(horizontal: 12, vertical: 6),
          child: Text(
            label,
            style: const TextStyle(color: Colors.white, fontSize: 12),
          ),
        ),
      ),
    );
  }
}
