function trigger_recording(src, evt, args)
%    disp('Start triggered')
%    disp(['Got event: ' evt.EventName])
%     #check if socket is setup
%         if not: warning/start_zmq
%         
    global socket
    global recording_armed
    % global socketstim
    if src.hSI.acqState ~= "focus" && ~src.hSI.hStackManager.enable
        disp('Start triggered')
        disp(['Got event: ' evt.EventName])
        disp('Sending')
        socket.send("start")
        % socketstim.send("start")
        recording_armed = true
    end
end
