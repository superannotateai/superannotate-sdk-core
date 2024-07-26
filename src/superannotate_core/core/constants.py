ATTACHING_UPLOAD_STATE_ERROR = "You cannot attach URLs in this type of project. Please attach it in an external storage project."
ATTACH_FOLDER_LIMIT_ERROR_MESSAGE = "The number of items you want to attach exceeds the limit of 50 000 items per folder."
ATTACH_PROJECT_LIMIT_ERROR_MESSAGE = "The number of items you want to attach exceeds the limit of 500 000 items per project."
ATTACH_USER_LIMIT_ERROR_MESSAGE = "The number of items you want to attach  exceeds the limit of your subscription plan."
ANNOTATION_FILE_SIZE_THRESHOLD = 15 * 1024 * 1024  # 15 MB
SMALL_ANNOTATIONS_MEMERY_LIMIT = 3 * ANNOTATION_FILE_SIZE_THRESHOLD
LARGE_ANNOTATIONS_MEMERY_LIMIT = 5 * ANNOTATION_FILE_SIZE_THRESHOLD
PROJECT_SETTINGS_VALID_ATTRIBUTES = [
    "Brightness",
    "Fill",
    "Contrast",
    "ShowLabels",
    "ShowComments",
    "Image",
    "Lines",
    "AnnotatorFinish",
    "PointSize",
    "FontSize",
    "WorkflowEnable",
    "ClassChange",
    "ShowEntropy",
    "UploadImages",
    "DeleteImages",
    "Download",
    "RunPredictions",
    "RunSegmentations",
    "ImageQuality",
    "ImageAutoAssignCount",
    "FrameMode",
    "FrameRate",
    "JumpBackward",
    "JumpForward",
    "UploadFileType",
    "Tokenization",
    "ImageAutoAssignEnable",
]
SPECIAL_CHARACTERS_IN_PROJECT_FOLDER_NAMES = set('/\\:*?"<>|“')
