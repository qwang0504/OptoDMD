function start_zmq(zeromq_jar_path, zeromq_protocol, zeromq_host, zeromq_port)
    
    javaclasspath(zeromq_jar_path)

    import org.zeromq.*;

    address = zeromq_protocol + zeromq_host + ":" + string(zeromq_port)

    context = ZContext();
    global socket
    socket = context.createSocket(ZMQ.PUB); 
    success = false;
    while(~success)
        success = socket.bind(address);
    end
    socket.setTCPKeepAlive(1);
    disp('bound trigger socket') 

    % % context = ZContext();
    % global socketstim
    % socketstim = context.createSocket(ZMQ.PUB); 
    % success = false;
    % while(~success)
    %     success = socketstim.bind(address);
    % end
    % socketstim.setTCPKeepAlive(1);

