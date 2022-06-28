import argparse
import yaml
import re
import os
from yaml.loader import Loader
from diagrams import Diagram, Cluster, Edge
from diagrams.aws.compute import EC2, Lambda, LambdaFunction, EC2AutoScaling, ECS, \
    ElasticContainerServiceContainer, ElasticContainerServiceService
from diagrams.aws.management import CloudformationStack
from diagrams.aws.storage import S3
from diagrams.aws.security import ACM, IAMPermissions, IAMRole, Cognito
from diagrams.aws.network import APIGateway, CloudFront, VPC, Route53HostedZone, InternetGateway, TransitGateway, \
    NATGateway, RouteTable, Nacl, PrivateSubnet, PublicSubnet, ELB
from diagrams.aws.general import User
from diagrams.aws.mobile import APIGateway
from diagrams.aws.database import DynamodbTable
from diagrams.aws.analytics import Kinesis
from diagrams.aws.integration import StepFunctions, SimpleQueueServiceSqsQueue


def yaml_constructor_intrinsic(loader, node):
    return {
        '__intrinsic': loader.construct_scalar(yaml.ScalarNode('fn', node.tag)),
        'logical_id': loader.construct_scalar(yaml.ScalarNode('fn', node.value)),
        'source': loader.construct_scalar(yaml.ScalarNode('fn', f'{node.tag} {node.value}')),
    }


parser = argparse.ArgumentParser(description='Draw AWS Schema base on CloudFormation stack.')
parser.add_argument('-n', '--name', type=str, help='Add name on the schema')
parser.add_argument('-i', '--input', required=True, type=str, help='File of parent stack as YAML file')
parser.add_argument('-o', '--output', required=True, type=str, help='Filename of output')
parser.add_argument('-f', '--format', required=True, type=str, default="png", help='file format')

for intrinsic in ['!Ref', '!Sub', '!GetAtt', '!Base64', '!Cidr', '!If', '!And', '!Or', '!Equals', '!FindInMap',
                  '!GetAtt', '!GetAZs', '!ImportValue', '!Join', '!Select', '!Split', '!Transform', '!Not',
                  'Fn::Ref', 'Fn::Sub', 'Fn::GetAtt', 'Fn::Base64', 'Fn::Cidr', 'Fn::If', 'Fn::And', 'Fn::Or',
                  'Fn::Equals', 'Fn::FindInMap', 'Fn::GetAtt', 'Fn::GetAZs', 'Fn::ImportValue', 'Fn::Join',
                  'Fn::Select', 'Fn::Split', 'Fn::Transform', 'Fn::Not']:
    Loader.add_implicit_resolver(intrinsic, re.compile(rf'^{intrinsic}\s.*$'), intrinsic)
    Loader.add_constructor(intrinsic, yaml_constructor_intrinsic)


def main():
    args = parser.parse_args()
    ast = parse_aws_stack(args.input)
    stack_path = os.path.dirname(args.input)

    with Diagram(args.name, filename=args.output, outformat=args.format):
        parse_aws_resources(ast['Resources'], stack_path)


def parse_aws_resources(ast_resources, stack_path):
    resources = {}

    for logical_id in ast_resources:
        resource_type = ast_resources[logical_id]['Type']
        name = logical_id
        if 'Name' in ast_resources[logical_id]:
            name = ast_resources[logical_id]['Name']
        resources[logical_id] = draw_resource(resource_type, name)

        if 'AWS::CloudFormation::Stack' == resource_type:
            child_stack_file = f"{stack_path}/{ast_resources[logical_id]['Properties']['TemplateURL']}"
            ast_child = parse_aws_stack(child_stack_file)
            with Cluster(name):
                child_resources = parse_aws_resources(ast_child['Resources'], os.path.dirname(child_stack_file))
                child_nodes = []
                for k, v in child_resources.items():
                    if v is not None:
                        child_nodes.append(v)
                resources[logical_id] \
                    - Edge(color="brown", style="dotted") \
                    >> child_nodes

        # Detect link !Ref
        links = link_discovery(ast_resources[logical_id])
        for link in links:
            if link in resources and resources[logical_id] and resources[link]:
                resources[logical_id] << resources[link]

    return resources


def parse_aws_stack(path):
    with open(path, 'r') as f:
        return list(yaml.load_all(f, Loader=Loader))[0]


def link_discovery(node):
    links = []

    if type(node) is not dict:
        raise Exception('Node has to be a dictionary')

    for k, v in node.items():
        if type(v) is not dict:
            continue
        if '__intrinsic' in v and v['__intrinsic'] == '!Ref':
            links.append(v['logical_id'])
            continue
        links = [*links, *link_discovery(v)]

    return list(dict.fromkeys(links))


def draw_resource(type, name):
    if 'AWS::CloudFormation::Stack' == type:
        return CloudformationStack(name)

    if 'AWS::S3::Bucket' == type:
        return S3(name)

    if 'AWS::CertificateManager::Certificate' == type:
        return ACM(name)

    if 'AWS::Serverless::HttpApi' == type:
        return APIGateway(name)

    if 'AWS::Serverless::Function' == type or 'AWS::Lambda::Function' == type:
        return Lambda(name)

    if 'Type::Custom::SSM' == type:
        return LambdaFunction(name)

    if 'AWS::CloudFront::Distribution' == type:
        return CloudFront(name)

    if 'AWS::S3::BucketPolicy' == type:
        return IAMPermissions(name)

    if 'AWS::IAM::User' == type:
        return User(name)

    if 'AWS::EC2::Instance' == type:
        return EC2(name)

    if 'AWS::AutoScaling::AutoScalingGroup' == type:
        return EC2AutoScaling(name)

    if 'AWS::EC2::VPC' == type:
        return VPC(name)

    if 'AWS::Route53::HostedZone' == type:
        return Route53HostedZone(name)

    if 'AWS::EC2::InternetGateway' == type:
        return InternetGateway(name)

    if 'AWS::EC2::TransitGateway' == type:
        return TransitGateway(name)

    if 'AWS::EC2::NatGateway' == type:
        return NATGateway(name)

    if 'AWS::EC2::RouteTable' == type:
        return RouteTable(name)

    if 'AWS::EC2::NetworkAcl' == type:
        return Nacl(name)

    if 'AWS::EC2::Subnet' == type:
        return PrivateSubnet(name)

    if 'AWS::ElasticLoadBalancingV2::LoadBalancer' == type:
        return ELB(name)

    if 'AWS::IAM::Role' == type:
        return IAMRole(name)

    if 'AWS::Cognito::UserPool' == type:
        return Cognito(name)

    if 'AWS::ApiGateway::RestApi' == type:
        return APIGateway(name)

    if 'AWS::ApiGateway::HttpApi' == type:
        return APIGateway(name)

    if 'AWS::DynamoDB::Table' == type:
        return DynamodbTable(name)

    if 'AWS::ECS::Cluster' == type:
        return ECS(name)

    if 'AWS::IAM::Policy' == type:
        return IAMPermissions(name)

    if 'AWS::ECS::TaskDefinition' == type:
        return ElasticContainerServiceContainer(name)

    if 'AWS::ECS::Service' == type:
        return ElasticContainerServiceService(name)

    if 'AWS::Kinesis::Stream' == type:
        return Kinesis(name)

    if 'AWS::StepFunctions::StateMachine' == type:
        return StepFunctions(name)

    if 'AWS::SQS::Queue' == type:
        return SimpleQueueServiceSqsQueue(name)

    print(f"[INFO] Resource Type {type} is not supported")


main()
