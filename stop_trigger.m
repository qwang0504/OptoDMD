function trigger_recording(src, evt, args)
    disp('Stop triggered')
    disp(['Got event: ' evt.EventName])
%     #check if socket is setup
%         if not: wanring/start_zmq
%         
    global socket
    % global socketstim
    if src.hSI.acqState = "Abort"
        disp('Sending')
        socket.send("stop")
        % socketstim.send("start")
    end
end
