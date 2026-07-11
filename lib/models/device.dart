enum DeviceStatus { online, offline }

class Device {
  const Device({
    required this.deviceId,
    required this.name,
    required this.status,
  });

  final String deviceId;
  final String name;
  final DeviceStatus status;

  bool get isOnline => status == DeviceStatus.online;

  factory Device.fromJson(Map<String, dynamic> json) {
    final raw = (json['status'] as String? ?? 'offline').toLowerCase();
    return Device(
      deviceId: json['device_id'] as String? ?? json['deviceId'] as String,
      name: json['device_name'] as String? ??
          json['name'] as String? ??
          json['device_id'] as String? ??
          'Computer',
      status: raw == 'online' ? DeviceStatus.online : DeviceStatus.offline,
    );
  }

  Map<String, dynamic> toJson() => {
        'device_id': deviceId,
        'device_name': name,
        'status': status == DeviceStatus.online ? 'online' : 'offline',
      };

  Device copyWith({String? name, DeviceStatus? status}) {
    return Device(
      deviceId: deviceId,
      name: name ?? this.name,
      status: status ?? this.status,
    );
  }
}
