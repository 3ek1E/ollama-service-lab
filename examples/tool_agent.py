"""Real native function calling with a strict arithmetic tool, no eval/shell.

python examples/tool_agent.py "请使用calculate计算(123+456)*7，然后告诉我结果。"
"""
import ast
import json
import operator
import os
import sys
from call_four_apis import text_of
import urllib.request

OPS = {ast.Add: operator.add, ast.Sub: operator.sub, ast.Mult: operator.mul,
       ast.Div: operator.truediv, ast.USub: operator.neg, ast.UAdd: operator.pos}


def calculate(expression):
    if not isinstance(expression, str) or len(expression) > 120:
        raise ValueError('Expression too long or invalid')
    tree = ast.parse(expression, mode='eval')
    if sum(1 for _ in ast.walk(tree)) > 60:
        raise ValueError('Expression too complex')
    def visit(node):
        if isinstance(node, ast.Expression):
            return visit(node.body)
        if isinstance(node, ast.Constant) and type(node.value) in (int, float):
            value = node.value
        elif isinstance(node, ast.BinOp) and type(node.op) in OPS:
            value = OPS[type(node.op)](visit(node.left), visit(node.right))
        elif isinstance(node, ast.UnaryOp) and type(node.op) in OPS:
            value = OPS[type(node.op)](visit(node.operand))
        else:
            raise ValueError('Only numbers, parentheses, + - * / are allowed')
        if abs(value) > 1e15:
            raise ValueError('Result out of range')
        return value
    return visit(tree)


def solve(question):
    base = os.environ.get('SERVICE_BASE_URL', 'http://127.0.0.1:8088').rstrip('/')
    key = os.environ.get('SERVICE_API_KEY', 'ollama')
    messages = [{'role': 'system', 'content': '你是计算助手。数学问题必须调用calculate工具，得到结果后简短作答。'},
                {'role': 'user', 'content': question}]
    tools = [{'type': 'function', 'function': {'name': 'calculate', 'description': '精确计算四则运算表达式',
              'parameters': {'type': 'object', 'properties': {'expression': {'type': 'string'}}, 'required': ['expression']}}}]
    trace = []
    opener = urllib.request.build_opener(urllib.request.ProxyHandler({})) if urllib.parse.urlsplit(base).hostname in ('localhost', '127.0.0.1', '::1') else urllib.request.build_opener()
    for _ in range(4):
        payload = {'model': os.environ.get('OLLAMA_MODEL', 'qwen3.5:0.8b'), 'messages': messages,
                   'stream': False, 'think': False, 'tools': tools, 'options': {'temperature': 0, 'num_predict': 256}}
        req = urllib.request.Request(base+'/api/chat', json.dumps(payload).encode(),
                                     {'Content-Type': 'application/json', 'Authorization': 'Bearer '+key})
        with opener.open(req, timeout=180) as response:
            value = json.load(response)
        message = value['message']
        messages.append(message)
        if not message.get('tool_calls'):
            return {'answer': text_of('ollama', value), 'tools_executed': len(trace), 'trace': trace}
        for call in message['tool_calls'][:4]:
            function = call['function']
            if function['name'] != 'calculate':
                result = {'error': 'Tool not permitted'}
            else:
                try:
                    result = {'value': calculate(function['arguments']['expression'])}
                except (ValueError, SyntaxError, KeyError, ZeroDivisionError, TypeError, OverflowError) as exc:
                    result = {'error': str(exc)}
            trace.append({'tool': function['name'], 'arguments': function['arguments'], 'result': result})
            messages.append({'role': 'tool', 'tool_name': function['name'], 'content': json.dumps(result)})
    raise RuntimeError('Tool call budget exhausted')


if __name__ == '__main__':
    print(json.dumps(solve(' '.join(sys.argv[1:]) or '请使用calculate计算(123+456)*7，然后告诉我结果。'), ensure_ascii=False, indent=2))
