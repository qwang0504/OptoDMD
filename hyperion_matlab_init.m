%scanimage_folder='C:\Program Files\Vidrio\SI-Premium_2020.1.2_(2021-02-09)_bd806fcff6';
optoDMD_folder='C:\Users\wangqing\Code\OptoDMD';
zeromq_jar_path = 'C:\Users\wangqing\Code\OptoDMD\jeromq-0.6.0.jar';
zeromq_protocol = "tcp://";
zeromq_host = "*";
zeromq_port = 5572;
channel = 1;

% add scanimage path
%addpath(genpath(scanimage_folder));
addpath(genpath(optoDMD_folder));

% cd to optodmd
cd(optoDMD_folder)

% run scanimage
scanimage
ipc = frameDoneIPC(zeromq_jar_path, zeromq_protocol, zeromq_host, zeromq_port, channel);
