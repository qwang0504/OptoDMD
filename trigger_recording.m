function trigger_recording(src, evt, args)
    disp('Triggered')
%     #check if socket is setup
%         if not: wanring/start_zmq
%         
    global socket
    % global socketstim
    if src.hSI.acqState ~= "focus"
        disp('Sending')
        socket.send("start")
        % socketstim.send("start")
    end
end
