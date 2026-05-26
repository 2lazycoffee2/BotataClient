import logging 
import sys 
from pathlib import Path 

from botata_client .utils .constants import APP_NAME 


def setup_logger (
name :str =APP_NAME ,
level :int =logging .DEBUG ,
log_file :Path |None =None ,
)->logging .Logger :

    logger =logging .getLogger (name )
    logger .setLevel (level )


    if logger .handlers :
        return logger 


    formatter =logging .Formatter (
    fmt ="%(asctime)s │ %(levelname)-8s │ %(name)-20s │ %(message)s",
    datefmt ="%H:%M:%S",
    )


    console_handler =logging .StreamHandler (sys .stdout )
    console_handler .setLevel (level )
    console_handler .setFormatter (formatter )
    logger .addHandler (console_handler )


    if log_file :
        log_file .parent .mkdir (parents =True ,exist_ok =True )
        file_handler =logging .FileHandler (log_file ,encoding ="utf-8")
        file_handler .setLevel (level )
        file_handler .setFormatter (formatter )
        logger .addHandler (file_handler )

    return logger 



log =setup_logger ()
