class CarrotAgentBaseException(Exception):
    pass


class LLMException(CarrotAgentBaseException):
    pass


class AgentException(CarrotAgentBaseException):
    pass


class ConfigException(CarrotAgentBaseException):
    pass


class ToolException(CarrotAgentBaseException):
    pass
