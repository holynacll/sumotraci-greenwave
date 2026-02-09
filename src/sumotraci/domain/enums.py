from enum import Enum


class SeverityEnum(str, Enum):
    CRITICAL = 'CRITICAL'
    HIGH = 'HIGH'
    MEDIUM = 'MEDIUM'
    LOW = 'LOW'


class StatusEnum(str, Enum):
    ON_THE_WAY = 'ON_THE_WAY'
    IN_THE_ACCIDENT = 'IN_THE_ACCIDENT'
    TO_THE_HOSPITAL = 'TO_THE_HOSPITAL'
