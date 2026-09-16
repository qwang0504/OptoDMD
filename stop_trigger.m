function stop_trigger(src, evt, args)
    disp('Stop triggered')
    disp(['Got event: ' evt.EventName])
%     #check if socket is setup
%         if not: wanring/start_zmq
%         
    global socket
    global recording_armed

    % global socketstim
     if isempty(recording_armed) || ~recording_armed
        return
    end

    disp(['Stop triggered by: ' evt.EventName])
    socket.send(uint8('stop'));
    recording_armed = false;
end

%     if src.hSI.acqState = "Abort"
%         disp('Sending')
%         socket.send("stop")
%         % socketstim.send("start")
%     end
% end
