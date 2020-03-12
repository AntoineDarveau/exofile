class GetCustomFileWarning(UserWarning):
    
    def __init__(self, message=None, err=None):
        
        if message is None:
             message = "DID NOT READ CUSTOM TABLE. {} has occur "  \
               + "when trying to query/read the custom table."
                
        if err is None:
            err = 'UnspecifiedException'
        else:
            err = err.__class__.__name__
        
        # Print error name in message
        message = message.format(err)
            
        super().__init__(message)
        
class QueryFileWarning(UserWarning):
    
    def __init__(self, message=None, file=None, err=None):
        
        if message is None:
            message = "QUERY {} FAILED. {} has occur "  \
                    + "when trying to query {}."
            
        if err is None:
            err = 'UnspecifiedException'
        else:
            err = err.__class__.__name__
            
        if file is None:
            file = 'unspecified file'
            
        # Print error name in message
        message = message.format(file.upper(), err, file)
        
        super().__init__(message)