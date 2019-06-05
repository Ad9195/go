#!/usr/bin/expect

set timeout 120
set ip [lindex {{ tel_ip }}]
set port [lindex {{ tel_port }}]
set user [lindex {{ tel_user }}]
set password [lindex {{ tel_pass }}]
set su_pass [lindex {{ sudo_pass }}]

spawn telnet $ip $port
expect "'^]'.";
send "\r";

expect "login:"
send $user
send "\r"
expect "Password:"
send $password
send "\r"

sleep 1

send "sudo goes toggle";
send "\r";
expect "platina:"
send $su_pass
send "\r"

sleep 1

send "\r"

sleep 1



send "toggle\r"
send "\r"

sleep 1

send "\r\r"
expect "$"
send "exit\r"
send "\r"
sleep 1
send "\r"

