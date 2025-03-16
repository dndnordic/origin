# Distributed Cluster Architecture

The infrastructure is implemented as three independent Kubernetes clusters that work together to provide security, redundancy, and resilience for both Origin (governance) and Singularity (AI) systems. Each physical cluster hosts both systems in separate namespaces with strict isolation controls.

## Cluster Structure

### Alpha Cluster
- **Location**: Vultr Frankfurt (EU Central)
- **Network**: Isolated network zone with dedicated firewall
- **Production Namespaces**:
  - `origin-system`: Primary vault service and governance API
  - `singularity-system`: Identical Singularity workloads (1/3)
  - `monitoring`: Shared monitoring stack
- **Testing Namespaces**:
  - `origin-dev`: Development version of Origin
  - `origin-stage`: Staging environment for pre-production testing
  - `singularity-dev`: Development version of Singularity
  - `singularity-stage`: Staging environment for pre-production testing
  - `test-infra`: Testing infrastructure and tools
- **Origin Role**: Main decision-making cluster for governance
- **Singularity Role**: Redundant instance with identical capabilities
- **Status**: `kubectl -n monitoring get pods -l cluster=alpha`

### Beta Cluster 
- **Location**: Vultr Amsterdam (EU West)
- **Network**: Different EU availability zone for disaster resilience
- **Production Namespaces**:
  - `origin-system`: Secondary vault with verification capabilities
  - `singularity-system`: Identical Singularity workloads (2/3)
  - `data-storage`: Primary data persistence layer
- **Testing Namespaces**:
  - `origin-regression`: Automated regression testing environment
  - `singularity-regression`: Automated regression testing environment
  - `integration-tests`: Cross-system integration testing
- **Origin Role**: Verification and validation of Alpha decisions
- **Singularity Role**: Redundant instance with identical capabilities
- **Status**: `kubectl -n monitoring get pods -l cluster=beta`

### Gamma Cluster
- **Location**: Vultr Paris (EU West)
- **Network**: Third EU availability zone for fault isolation
- **Production Namespaces**:
  - `origin-system`: Tertiary vault and long-term audit logging
  - `singularity-system`: Identical Singularity workloads (3/3)
  - `backup-system`: Database backups and snapshots
- **Testing Namespaces**:
  - `experimental`: Testing experimental features
  - `performance-testing`: Load and performance testing
  - `security-testing`: Security validation tests
- **Origin Role**: Tie-breaker for consensus disagreements
- **Singularity Role**: Redundant instance with identical capabilities
- **Status**: `kubectl -n monitoring get pods -l cluster=gamma`

### Namespace Isolation and Security
- Each namespace has dedicated service accounts
- Network policies enforce strict isolation between namespaces
- Resource quotas prevent resource competition
- Different security contexts for Origin vs Singularity workloads
- Independent scaling rules per namespace

### Policy Enforcement
- **Open Policy Agent (OPA)** deployed as admission controller
- Policies defined as code in Rego language
- Automated validation of resources against security policies
- Pre-deployment policy checks in CI/CD pipeline
- Runtime policy enforcement via Gatekeeper
- Custom policy library for Origin/Singularity requirements:
  - Pod security standards enforcement
  - Network policy validation
  - Resource limits validation
  - Image source verification
  - Secret usage validation
- Policy violations trigger automated alerts and enforcement

### Monitoring and Backup Systems

#### Docker Builder Node
- **Role**: Primary monitoring and emergency management system
- **Location**: Linux builder server in private datacenter
- **Capabilities**:
  - Comprehensive monitoring of all clusters and namespaces
  - Connected to all clusters via Headscale VPN but not part of consensus
  - Can initiate emergency protocols if clusters become compromised
  - Maintains independent audit logs of all operations
  - Serves as emergency control plane if all clusters are compromised
  - Build system for creating and validating container images

#### Mikael's Machine (MIKKI-BUNKER)
- **Role**: GPU provider for token generation and LLM operations
- **Hardware**: Contains NVIDIA RTX 4080 for efficient token processing
- **Location**: Behind secure firewall with Headscale connection
- **Capabilities**:
  - Cost-effective generation of LLM tokens
  - Not part of the control system or monitoring infrastructure
  - Provides specialized AI compute resources on demand
  - Functions as dedicated resource for LLM operations

## Multi-System Architecture

### Relationship Between Origin and Singularity
- Origin governs Singularity via approval workflows and resource controls
- Singularity workloads run in dedicated namespaces on the same physical clusters
- Network policies allow controlled communication between systems
- Resource quotas ensure fair allocation and prevent denial of service

### Service Mesh Architecture
- **Istio service mesh** deployed across all clusters
- End-to-end mutual TLS (mTLS) encryption for all service communication
- Traffic management with intelligent routing capabilities
- Automatic sidecar injection in all namespaces
- Cross-cluster service connectivity through east-west gateways
- Fine-grained access control through Authorization Policies
- Traffic visualization and monitoring through Kiali dashboard
- Distributed tracing with Jaeger integration
- Metrics collection with Prometheus integration
- Circuit breaking and outlier detection for enhanced resilience

### Resource Allocation Strategy
- **Origin Priority**: Origin receives absolute priority for all resources
- **Resource Quotas**: Higher resource quotas for Origin namespaces
- **QoS Classes**: Origin pods get Guaranteed QoS class, Singularity gets Burstable
- **Pod Disruption Budget**: Stricter PDBs for Origin components
- **Node Selectors**: Origin can run on any node, Singularity limited to specific nodes
- **Preemption**: Kubernetes configured to preempt Singularity pods if Origin needs resources
- **Resource Limits**: Strict limits on Singularity resource consumption
- **Emergency Protocols**: Can suspend all Singularity workloads instantly if needed

### Singularity Resource Management
- Identical workloads run across all three clusters
- Load balancing distributes traffic to all Singularity instances
- Auto-scaling based on demand but with strict upper limits
- Each namespace has guaranteed minimum resources
- All resource requests must be approved by Origin

### Testing and Deployment Pipeline

#### Development-to-Production Pipeline
1. **Development Phase** (`origin-dev`, `singularity-dev` namespaces)
   - Active development work
   - Unit tests run automatically
   - Minimal resource allocation
   - Frequent deployments throughout the day
   
2. **Staging Phase** (`origin-stage`, `singularity-stage` namespaces)
   - Pre-production testing
   - Integration tests run automatically
   - Configuration matches production
   - Daily deployments from development
   
3. **Regression Testing** (`origin-regression`, `singularity-regression` namespaces)
   - Automated regression test suites
   - Performance baseline validation
   - Security validation tests
   - Weekly deployments from staging
   
4. **Production Deployment** (`origin-system`, `singularity-system` namespaces)
   - Identical workloads across all three clusters
   - Updates apply one cluster at a time in sequence
   - Alpha → Beta → Gamma update sequence
   - Health checks verify stability before continuing
   - Automated rollback if health checks fail
   - Blue/Green deployment within each cluster

## Consensus and Operational Model

### Basic System Operation
- Origin system requires at least 2 clusters to be operational at all times
- If fewer than 2 clusters are available, the Origin system enters lockdown mode
- Singularity can continue operating with reduced capacity even in lockdown
- Non-sensitive operations can continue with 2/3 clusters running
- All cluster status changes are logged and alerts generated

### Consensus Decision Model
The Origin system uses a 2-of-3 consensus model for all security-sensitive operations:

1. When a sensitive operation is requested:
   - The request is sent to the Alpha cluster's Origin namespace
   - Alpha forwards verification requests to Beta and Gamma Origin namespaces
   - At least one other cluster must approve the operation
   - The operation proceeds only with 2/3 approval

2. For critical operations (credential management, governance rules):
   - All three Origin namespaces must verify and approve
   - Any single Origin instance can veto the operation
   - Results are logged in all three audit logs

### Degraded Operation Protocol
If a cluster becomes unavailable:
   - Remaining clusters automatically detect failure
   - Origin namespaces in operational clusters continue governance
   - Singularity workloads are redistributed to remaining clusters
   - Non-critical operations continue with 2 running clusters
   - Critical governance decisions require Mikael's manual approval
   - Automatic repair process attempts to restore the third cluster
   - System returns to normal when all 3 clusters are operational

## Deployment Strategy

To maintain security during updates:

1. **Geographically Distributed Deployment**
   - Each cluster is deployed in a different Vultr region
   - Network isolation between clusters with secure VPN tunnels
   - Independent infrastructure for each cluster
   - Different network security configurations per region
   - Mitigates region-specific outages and attacks

2. **GitOps Workflow**
   - ArgoCD deployed to each cluster for GitOps-based deployments
   - Git repository as single source of truth for all configurations
   - Automatic synchronization between Git state and cluster state
   - Drift detection with automated reconciliation
   - Full audit trail of all configuration changes through Git history
   - Separate ArgoCD projects for Origin and Singularity workloads
   - Progressive GitOps with hierarchical app delivery

3. **Progressive Deployment**
   - Updates are applied one cluster at a time
   - Alpha is updated first, then Beta, then Gamma
   - Each update is verified by the other clusters before proceeding
   - ArgoCD promotes changes between environments after validation

4. **Canary Deployments**
   - Flagger controller deployed for advanced canary analysis
   - Metric-based promotion criteria (error rates, latency, etc.)
   - Automatic traffic shifting in incremental steps
   - Automated rollback if metrics fall below thresholds
   - Progressive delivery tied into GitOps workflow

5. **Verification Process**
   - Each update is cryptographically signed
   - Non-updated clusters verify the signature
   - Security checks run against the updated cluster
   - Full system tests between update stages
   - Automatic policy compliance verification

6. **Rollback Capability**
   - Each cluster maintains previous state in snapshots
   - Automatic rollback if consensus is lost
   - ArgoCD rollbacks to any previous working state
   - Manual rollback option for Mikael (emergency use)

## Security and Emergency Procedures

### Mikael's YubiKey Security
- Single YubiKey serves as the master security control
- Required for all administrative access to clusters
- Unlocks emergency recovery procedures
- Physically secured by Mikael at all times
- Backup procedures documented if YubiKey is lost

### System Logging
- Comprehensive logging of all operations across clusters
- Central audit trail accessible to Mikael
- Logs retained for security review and troubleshooting
- Automated log analysis for suspicious patterns

### Real-time Monitoring
- Each cluster monitors the others for health checks
- Automatic alerts if consensus cannot be reached
- Metrics collection for all inter-cluster communications
- Automatic failover if a cluster becomes unresponsive

### Emergency Failsafe Protocol
- If only 1 cluster remains operational, system enters lockdown mode
- All governance operations are suspended
- Only read-only operations are permitted
- Mikael must manually approve any system changes using YubiKey
- Emergency recovery plan is activated
- Status alerts sent through multiple channels (email, SMS, messenger)

### Update Process
- Updates prepared in development environment
- Verified by automated test suites
- Mikael approves all updates before deployment
- Staged rollout with automated verification at each step

### Degradation Management
- System gracefully degrades functionality in case of failures
- Automatic attempts to restore service when possible
- Clear alerts when manual intervention is required
- Documented recovery procedures for common failure modes