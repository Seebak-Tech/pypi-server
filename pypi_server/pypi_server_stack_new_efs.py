from aws_cdk import (
    aws_autoscaling as autoscaling,
    aws_ec2 as ec2,
    aws_ecs as ecs,
    aws_efs as efs,
    #  aws_iam as iam,
    aws_elasticloadbalancingv2 as elbv2,
    CfnParameter, CfnOutput, Duration, Stack,
)
from constructs import Construct


class PypiServerStack(Stack):

    def __init__(self, scope: Construct, construct_id: str, **kwargs) -> None:
        super().__init__(scope, construct_id, **kwargs)

        # The code that defines your stack goes here

        # ==============================
        # ======= CFN PARAMETERS =======
        # ==============================
        project_name_param = CfnParameter(
            scope=self,
            id='ProjectName',
            type='String',
            default='pypiserver'
        )

        container_repo_name = 'pypiserv-containers'
        cluster_name = 'pypiserv_clus'
        service_name = 'pypiserv_serv'

        # ==================================================
        # ================= IAM ROLE =======================
        # ==================================================
        #  role = iam.Role(
            #  scope=self,
            #  id='TASKROLE',
            #  assumed_by=iam.ServicePrincipal(service='ecs-tasks.amazonaws.com')
        #  )
#
        #  role.add_managed_policy(
            #  iam.ManagedPolicy
               #  .from_aws_managed_policy_name('AmazonS3FullAccess')
        #  )
#
        #  role.add_managed_policy(
            #  iam.ManagedPolicy
               #  .from_aws_managed_policy_name('AmazonECS_FullAccess')
        #  )
#
        # ==================================================
        # ==================== VPC =========================
        # ==================================================
        nat_gateway_instance = ec2.NatProvider.instance(
            instance_type=ec2.InstanceType("t2.micro"),
            machine_image=ec2.GenericLinuxImage(
                ami_map={
                    'us-west-2': 'ami-0a4bc8a5c1ed3b5a3'
                }
            )
        )

        vpc = ec2.Vpc(
            scope=self,
            id='VPC',
            cidr='10.0.0.0/24',
            max_azs=2,
            nat_gateway_provider=nat_gateway_instance,
            nat_gateways=1
        )

        # ==================================================
        # =============== ECS SERVICE ==================
        # ==================================================
        # Create a Cluster
        cluster = ecs.Cluster(
            scope=self,
            id='CLUSTER',
            cluster_name=cluster_name,
            vpc=vpc
        )

        asg = autoscaling.AutoScalingGroup(
            scope=self,
            id='AutoScalingGroup',
            instance_type=ec2.InstanceType("t2.micro"),
            machine_image=ecs.EcsOptimizedImage.amazon_linux2(),
            vpc=vpc
        )
        capacity_provider = ecs.AsgCapacityProvider(
            scope=self,
            id="AsgCapacityProvider",
            auto_scaling_group=asg,
            enable_managed_termination_protection=False,
        )
        cluster.add_asg_capacity_provider(capacity_provider)

        #  Create EFS
        elasticfilestore = efs.FileSystem(
            scope=self,
            id="efs-demo",
            vpc=vpc,
            encrypted=False,
            lifecycle_policy=efs.LifecyclePolicy.AFTER_14_DAYS
        )
#
        sg_efs = ec2.SecurityGroup(
            scope=self,
            id="sg_efs",
            vpc=vpc,
            security_group_name="sg_efs"
        )

        sg_efs.add_ingress_rule(
            peer=ec2.Peer.ipv4("10.0.0.0/24"),
            connection=ec2.Port.tcp(2049)
        )

        # Create a Task Definition
        task_definition = ecs.Ec2TaskDefinition(
            scope=self,
            id='TaskDef'
        )
        container = task_definition.add_container(
            id='Pypiserver',
            image=ecs.ContainerImage.from_registry(
                "pypiserver/pypiserver:latest"
            ),
            memory_limit_mib=512,
            cpu=512
            #  essential=True
        )
        port_mapping = ecs.PortMapping(
            container_port=8080,
            host_port=80,
            protocol=ecs.Protocol.TCP
        )
        container.add_port_mappings(port_mapping)
        container.task_definition.add_volume(
            name='efs-volume',
            efs_volume_configuration=ecs.EfsVolumeConfiguration(
                file_system_id=elasticfilestore.file_system_id
            )
        )

        # Create a Service
        service = ecs.Ec2Service(
            scope=self,
            id='PYPISERVER',
            service_name=service_name,
            cluster=cluster,
            task_definition=task_definition
        )

        # Create ALB
        lb = elbv2.ApplicationLoadBalancer(
            scope=self,
            id="LB",
            vpc=vpc,
            internet_facing=True
        )
        listener = lb.add_listener(
            id="PublicListener",
            port=80,
            open=True
        )

        health_check = elbv2.HealthCheck(
            interval=Duration.seconds(60),
            path="/",
            timeout=Duration.seconds(5)
        )

        # Attach ALB to ECS Service
        listener.add_targets(
            id="ECS",
            port=80,
            targets=[asg],
            health_check=health_check
        )

        asg.user_data.add_commands(
            "yum check-update -y",
            "yum upgrade -y",
            "yum install -y amazon-efs-utils",
            "yum install -y nfs-utils",
            "file_system_id_1=" + elasticfilestore.file_system_id,
            "efs_mount_point_1=/data/packages",
            "mkdir -p \"${efs_mount_point_1}\"",
            "test -f \"/sbin/mount.efs\" && echo \"${file_system_id_1}:/ ${efs_mount_point_1} efs defaults,_netdev\" >> /etc/fstab || " +
            "echo \"${file_system_id_1}.efs." + Stack.of(self).region +
            ".amazonaws.com:/ ${efs_mount_point_1} nfs4 nfsvers=4.1,rsize=1048576,wsize=1048576,hard,timeo=600,retrans=2,noresvport,_netdev 0 0\" >> /etc/fstab",
            "mount -a -t efs,nfs4 defaults"
        )

        # ==================================================
        # =================== OUTPUTS ======================
        # ==================================================
        CfnOutput(
            scope=self,
            id='LoadBalancerDNS',
            value=lb.load_balancer_dns_name
        )
