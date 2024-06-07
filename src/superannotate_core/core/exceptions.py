class SABaseException(Exception):
    """
    Base exception for Superannotate SDK. All exceptions thrown by inviter should
    extend this.
    """

    def __init__(self, message):
        super().__init__(message)

        self.message = str(message)

    def __str__(self):
        return self.message


class SAException(Exception):

    def __init__(self, message):
        super().__init__(message)

        self.message = str(message)

    def __str__(self):
        return self.message


class SAInvalidInput(SAException):
    """
    Wrong input
    """


class SAValidationException(SAException):
    """
    Input validation
    """

