# Example UE registration output (Open5GS + UERANSIM)

```
Deploying component: 'ueransim-ue'
UERANSIM v3.2.6
[2026-09-08 13:03:39.350] [nas] [[32minfo[m] UE switches to state [MM-DEREGISTERED/PLMN-SEARCH]
[?2004h]0;root@c4d4483bde7a: /UERANSIM/buildroot@c4d4483bde7a:/UERANSIM/build# [2026-09-08 13:03:39.351] [rrc] [[36mdebug[m] New signal detected for cell[1], total [1] cells in coverage
[2026-09-08 13:03:39.351] [nas] [[32minfo[m] Selected plmn[001/01]
[2026-09-08 13:03:39.351] [rrc] [[32minfo[m] Selected cell plmn[001/01] tac[1] category[SUITABLE]
[2026-09-08 13:03:39.351] [nas] [[32minfo[m] UE switches to state [MM-DEREGISTERED/PS]
[2026-09-08 13:03:39.351] [nas] [[32minfo[m] UE switches to state [MM-DEREGISTERED/NORMAL-SERVICE]
[2026-09-08 13:03:39.351] [nas] [[36mdebug[m] Initial registration required due to [MM-DEREG-NORMAL-SERVICE]
[2026-09-08 13:03:39.351] [nas] [[36mdebug[m] UAC access attempt is allowed for identity[0], category[MO_sig]
[2026-09-08 13:03:39.351] [nas] [[36mdebug[m] Sending Initial Registration
[2026-09-08 13:03:39.351] [nas] [[32minfo[m] UE switches to state [MM-REGISTER-INITIATED]
[2026-09-08 13:03:39.351] [rrc] [[36mdebug[m] Sending RRC Setup Request
[2026-09-08 13:03:39.351] [rrc] [[32minfo[m] RRC connection established
[2026-09-08 13:03:39.351] [rrc] [[32minfo[m] UE switches to state [RRC-CONNECTED]
[2026-09-08 13:03:39.352] [nas] [[32minfo[m] UE switches to state [CM-CONNECTED]
[2026-09-08 13:03:39.359] [nas] [[36mdebug[m] Authentication Request received
[2026-09-08 13:03:39.359] [nas] [[36mdebug[m] Sending Authentication Failure due to SQN out of range
[2026-09-08 13:03:39.362] [nas] [[36mdebug[m] Authentication Request received
[2026-09-08 13:03:39.363] [nas] [[36mdebug[m] Security Mode Command received
[2026-09-08 13:03:39.363] [nas] [[36mdebug[m] Selected integrity[2] ciphering[0]
[2026-09-08 13:03:39.370] [nas] [[36mdebug[m] Registration accept received
[2026-09-08 13:03:39.370] [nas] [[32minfo[m] UE switches to state [MM-REGISTERED/NORMAL-SERVICE]
[2026-09-08 13:03:39.370] [nas] [[36mdebug[m] Sending Registration Complete
[2026-09-08 13:03:39.370] [nas] [[32minfo[m] Initial Registration is successful
[2026-09-08 13:03:39.370] [nas] [[36mdebug[m] Sending PDU Session Establishment Request
[2026-09-08 13:03:39.370] [nas] [[36mdebug[m] UAC access attempt is allowed for identity[0], category[MO_sig]
[2026-09-08 13:03:39.572] [nas] [[36mdebug[m] Configuration Update Command received
[2026-09-08 13:03:39.586] [nas] [[36mdebug[m] PDU Session Establishment Accept received
[2026-09-08 13:03:39.586] [nas] [[32minfo[m] PDU Session establishment is successful PSI[1]
[2026-09-08 13:03:39.600] [app] [[32minfo[m] Connection setup for PDU session[1] is successful, TUN interface[uesimtun0, 192.168.100.2] is up.
PING 8.8.8.8 (8.8.8.8) from 192.168.100.2 uesimtun0: 56(84) bytes of data.
64 bytes from 8.8.8.8: icmp_seq=1 ttl=113 time=19.1 ms
64 bytes from 8.8.8.8: icmp_seq=2 ttl=113 time=19.3 ms
64 bytes from 8.8.8.8: icmp_seq=3 ttl=113 time=21.5 ms
64 bytes from 8.8.8.8: icmp_seq=4 ttl=113 time=21.6 ms

--- 8.8.8.8 ping statistics ---
4 packets transmitted, 4 received, 0% packet loss, time 3003ms
rtt min/avg/max/mdev = 19.114/20.378/21.622/1.166 ms
```
