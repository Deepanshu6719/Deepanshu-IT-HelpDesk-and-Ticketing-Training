def example_response(description: str, example):
    return {
        "description": description,
        "content": {
            "application/json": {
                "example": example,
            },
        },
    }


def success_example_response(description: str, data):
    return example_response(
        description,
        {
            "success": True,
            "data": data,
        },
    )
