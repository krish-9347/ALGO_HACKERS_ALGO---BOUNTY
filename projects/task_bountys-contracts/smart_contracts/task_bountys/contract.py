from algopy import UInt64, gtxn, ARC4Contract, arc4, Global, itxn, BoxMap

class TaskData(arc4.Struct, frozen=True):
    company: arc4.Address
    freelancer: arc4.Address
    reward: arc4.UInt64

class DisputeData(arc4.Struct, frozen=False):
    freelancer_votes: arc4.UInt64
    company_votes: arc4.UInt64
    is_open: arc4.Bool
    voters: arc4.DynamicArray[arc4.Address]
    reward: arc4.UInt64
    client_amount_transferred: arc4.Bool
    freelancer_amount_transferred: arc4.Bool

class TaskBountyContract(ARC4Contract):
    def __init__(self) -> None:
        self.tasks = BoxMap(arc4.UInt64, TaskData, key_prefix="users")
        self.disputes = BoxMap(arc4.UInt64, DisputeData, key_prefix="disputes")

    @arc4.abimethod
    def create_task(
        self,
        payment_txn: gtxn.PaymentTransaction,
        task_id: arc4.UInt64,
        company: arc4.Address,
        freelancer: arc4.Address,
        reward: arc4.UInt64,
    ) -> None:
        assert payment_txn.receiver == Global.current_application_address
        assert payment_txn.amount >= reward.native
        assert payment_txn.sender == company.native
        self.tasks[task_id] = TaskData(company, freelancer, reward)

    @arc4.abimethod
    def release_reward(self, task_id: arc4.UInt64, caller: arc4.Address) -> UInt64:
        task = self.tasks[task_id]
        assert caller == task.company, "Only company can release"
        result = itxn.Payment(
            sender=Global.current_application_address,
            receiver=task.freelancer.native,
            amount=task.reward.native,
            fee=0,
        ).submit()
        del self.tasks[task_id]
        return result.amount

    @arc4.abimethod
    def start_appeal(self, task_id: arc4.UInt64, caller: arc4.Address) -> None:
        task = self.tasks[task_id]
        assert caller == task.company or caller == task.freelancer
        assert task_id not in self.disputes
        self.disputes[task_id] = DisputeData(
            freelancer_votes=arc4.UInt64(0),
            company_votes=arc4.UInt64(0),
            is_open=arc4.Bool(True),
            voters=arc4.DynamicArray[arc4.Address](),
            reward=task.reward,
            client_amount_transferred=arc4.Bool(False),
            freelancer_amount_transferred=arc4.Bool(False),
        )

    @arc4.abimethod
    def cast_vote(
        self, task_id: arc4.UInt64, vote_for_freelancer: arc4.Bool, caller: arc4.Address
    ) -> None:
        dispute = self.disputes[task_id].copy()
        assert dispute.is_open
        for voter in dispute.voters:
            assert caller != voter, "Already voted"
        if vote_for_freelancer:
            dispute.freelancer_votes = arc4.UInt64(dispute.freelancer_votes.native + 1)
        else:
            dispute.company_votes = arc4.UInt64(dispute.company_votes.native + 1)
        dispute.voters.append(caller)
        self.disputes[task_id] = dispute

    @arc4.abimethod
    def resolve_dispute(self, task_id: arc4.UInt64, caller: arc4.Address) -> UInt64:
        task = self.tasks[task_id]
        dispute = self.disputes[task_id].copy()
        assert dispute.is_open
        voter_reward_pool = arc4.UInt64(dispute.reward.native // 10) if dispute.voters.length > 0 else arc4.UInt64(0)
        reward_to_winner = arc4.UInt64(dispute.reward.native - voter_reward_pool.native)
        if dispute.freelancer_votes.native > dispute.company_votes.native:
            result = itxn.Payment(
                sender=Global.current_application_address,
                receiver=task.freelancer.native,
                amount=reward_to_winner.native,
                fee=0,
            ).submit()
            dispute.freelancer_amount_transferred = arc4.Bool(True)
            dispute.client_amount_transferred = arc4.Bool(True)
        elif dispute.freelancer_votes.native < dispute.company_votes.native:
            result = itxn.Payment(
                sender=Global.current_application_address,
                receiver=task.company.native,
                amount=reward_to_winner.native,
                fee=0,
            ).submit()
            dispute.client_amount_transferred = arc4.Bool(True)
            dispute.freelancer_amount_transferred = arc4.Bool(True)
        else:
            assert caller == task.company or caller == task.freelancer
            reward_half = arc4.UInt64(reward_to_winner.native // 2)
            if caller == task.company:
                dispute.client_amount_transferred = arc4.Bool(True)
            elif caller == task.freelancer:
                dispute.freelancer_amount_transferred = arc4.Bool(True)
            result = itxn.Payment(
                sender=Global.current_application_address,
                receiver=caller.native,
                amount=reward_half.native,
                fee=0,
            ).submit()
        if dispute.freelancer_amount_transferred and dispute.client_amount_transferred:
            del self.tasks[task_id]
            dispute.is_open = arc4.Bool(False)
        self.disputes[task_id] = dispute
        return result.amount

    @arc4.abimethod
    def claim_voting_reward(self, task_id: arc4.UInt64, caller: arc4.Address) -> UInt64:
        dispute = self.disputes[task_id].copy()
        voters = dispute.voters
        found = False
        new_voters = arc4.DynamicArray[arc4.Address]()
        for voter in voters:
            if voter == caller:
                found = True
            else:
                new_voters.append(voter)
        assert found, "Caller did not vote"
        total_reward = arc4.UInt64(dispute.reward.native // 10)
        share = arc4.UInt64(total_reward.native // voters.length)
        result = itxn.Payment(
            sender=Global.current_application_address,
            receiver=caller.native,
            amount=share.native,
            fee=0,
        ).submit()
        if new_voters.length == 0:
            del self.disputes[task_id]
        else:
            dispute.voters = new_voters
            self.disputes[task_id] = dispute
        return result.amount

  @arc4.abimethod
def task_exists(self, task_id: arc4.UInt64) -> arc4.Bool:
    return arc4.Bool(task_id in self.tasks)
 @arc4.abimethod
def reject_task(self, task_id: arc4.UInt64, caller: arc4.Address) -> None:
    task = self.tasks[task_id]
    assert caller == task.freelancer, "Only freelancer can reject task"
    refund_amount = task.reward.native
    itxn.Payment(
        sender=Global.current_application_address,
        receiver=task.company.native,
        amount=refund_amount,
        fee=0,
    ).submit()
    del self.tasks[task_id]

@arc4.abimethod
def get_dispute_status(self, task_id: arc4.UInt64) -> DisputeData:
    return self.disputes[task_id]


