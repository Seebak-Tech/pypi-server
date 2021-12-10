import aws_cdk as core
import aws_cdk.assertions as assertions

from pypi_server.pypi_server_stack import PypiServerStack

# example tests. To run these tests, uncomment this file along with the example
# resource in pypi_server/pypi_server_stack.py
def test_sqs_queue_created():
    app = core.App()
    stack = PypiServerStack(app, "pypi-server")
    template = assertions.Template.from_stack(stack)

#     template.has_resource_properties("AWS::SQS::Queue", {
#         "VisibilityTimeout": 300
#     })
