import argparse
import os
import sys

from dotenv import load_dotenv
from fastmcp import FastMCP
from fastmcp.server.auth.providers.jwt import JWTVerifier
from loguru import logger

from .constant import MCP_SERVER_VERSION
from .rabbitmq.module import RabbitMQModule


class RabbitMQMCPServer:
    def __init__(self, allow_mutative_tools: bool):
        # Setup logger
        logger.remove()
        logger.add(sys.stderr, level=os.getenv("FASTMCP_LOG_LEVEL", "WARNING"))
        self.logger = logger

        # Initialize FastMCP
        self.mcp = FastMCP(
            "mcp-server-rabbitmq",
            instructions="""Manage RabbitMQ message brokers and interact with queues and exchanges.""",
        )

        rmq_module = RabbitMQModule(self.mcp)
        rmq_module.register_rabbitmq_management_tools(allow_mutative_tools)

        # --- Automatic RabbitMQ Connection ---
        broker_hostname = os.getenv("RABBITMQ_HOSTNAME")
        username = os.getenv("RABBITMQ_USERNAME")
        password = os.getenv("RABBITMQ_PASSWORD")

        if broker_hostname and username and password:
            port = int(os.getenv("RABBITMQ_PORT", "5671"))
            management_port = int(os.getenv("RABBITMQ_MANAGEMENT_PORT", "15671"))
            use_tls = os.getenv("RABBITMQ_USE_TLS", "true").lower() == "true"
            verify_ssl = os.getenv("RABBITMQ_VERIFY_SSL", "true").lower() == "true"

            try:
                self.logger.info("Attempting automatic connection to RabbitMQ...")
                rmq_module.rabbitmq_broker_initialize_connection(
                    broker_hostname=broker_hostname,
                    username=username,
                    password=password,
                    port=port,
                    management_port=management_port,
                    use_tls=use_tls,
                    verify_ssl=verify_ssl,
                )
                self.logger.info("Successfully connected to RabbitMQ automatically.")
            except Exception as e:
                self.logger.error(f"Failed to connect to RabbitMQ automatically: {e}")
        else:
            self.logger.info("RabbitMQ connection environment variables not found. Skipping automatic connection.")
        # --- End Automatic RabbitMQ Connection ---

    def run(self, args):
        """Run the MCP server with the provided arguments."""
        self.logger.info(f"Starting RabbitMQ MCP Server v{MCP_SERVER_VERSION}")

        if args.http:
            if not args.no_auth:
                if not args.http_auth_jwks_uri:
                    raise ValueError("Please set --http-auth-jwks-uri")
                self.mcp.auth = JWTVerifier(
                    jwks_uri=args.http_auth_jwks_uri,
                    issuer=args.http_auth_issuer,
                    audience=args.http_auth_audience,
                    required_scopes=args.http_auth_required_scopes,
                )
            self.mcp.run(
                transport="http",
                host="0.0.0.0",
                port=args.server_port,
                path="/mcp",
            )
        else:
            transport_type = os.getenv("MCP_TRANSPORT_TYPE", "stdio")
            self.mcp.run(transport=transport_type)


def main():
    load_dotenv()
    """Run the MCP server with CLI argument support."""
    parser = argparse.ArgumentParser(
        description="A Model Context Protocol (MCP) server for RabbitMQ"
    )
    parser.add_argument(
        "--allow-mutative-tools",
        action="store_true",
        help="Enable tools that can mutate the states of RabbitMQ",
    )
    # Streamable HTTP specific configuration
    parser.add_argument("--http", action="store_true", help="Use Streamable HTTP transport")
    parser.add_argument(
        "--server-port", type=int, default=8888, help="Port to run the MCP server on"
    )
    parser.add_argument(
        "--http-auth-jwks-uri",
        type=str,
        default=os.getenv("HTTP_AUTH_JWKS_URI"),
        help="JKWS URI for FastMCP Bearer Auth Provider",
    )
    parser.add_argument(
        "--http-auth-issuer",
        type=str,
        default=os.getenv("HTTP_AUTH_ISSUER"),
        help="Issuer for FastMCP Bearer Auth Provider",
    )
    parser.add_argument(
        "--http-auth-audience",
        type=str,
        default=os.getenv("HTTP_AUTH_AUDIENCE"),
        help="Audience for FastMCP Bearer Auth Provider",
    )
    parser.add_argument(
        "--http-auth-required-scopes",
        nargs="*",
        default=os.getenv("HTTP_AUTH_REQUIRED_SCOPES", "").split(),
        help="Required scope for FastMCP Bearer Auth Provider",
    )
    parser.add_argument(
        "--no-auth",
        action="store_true",
        help="Disable authentication",
    )

    args = parser.parse_args()

    # Create server with connection parameters from args
    server = RabbitMQMCPServer(args.allow_mutative_tools)

    # Run the server with remaining args
    server.run(args)


if __name__ == "__main__":
    main()
