import re


def extract_data_from_braces(input_str):
    """
    提取字符串中所有完整的花括号内容，包括花括号本身。

    :param input_str: 包含花括号内容的字符串
    :return: 一个列表，包含所有匹配的花括号及其内容
    """
    # 匹配完整的花括号内容
    pattern = re.compile("{.*?}", re.S)

    # 使用 re.findall 提取所有符合条件的内容
    matches = re.findall(pattern, input_str)

    return matches


if __name__ == "__main__":
    # 示例
    input_text = """{xxx}{yyy}"""
    output = extract_data_from_braces(input_text)
    print(output)