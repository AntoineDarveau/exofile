class BaseFileWarning(UserWarning):
    
    def __init__(self, message, file=None, err=None):
        
        if message is None:
             message = ""
                
        if err is None:
            err = 'UnspecifiedException'
        else:
            err = err.__class__.__name__
        
        if file is None:
            file = 'unspecified file'
        
        # Print error name and file in message
        message = message.format(file.upper(), err, file)
            
        super().__init__(message)

class GetLocalFileWarning(BaseFileWarning):
    
    def __init__(self, message=None, file=None, err=None):
        
        if message is None:
             message = "DID NOT READ {}. {} has occur "  \
               + "when trying to query/read {}."
            
        super().__init__(message, file=file, err=err)
        
class QueryFileWarning(BaseFileWarning):
    
    def __init__(self, message=None, file=None, err=None):
        
        if message is None:
            message = "QUERY {} FAILED. {} has occur "  \
                    + "when trying to query {}."
        
        super().__init__(message, file=file, err=err)